import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { ExternalLink, KeyRound, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import {
  useCreateCheckoutSessionMutation,
  useCreatePortalSessionMutation,
  useGetAiSettingsQuery,
  usePutAiSettingsMutation,
} from "@/features/api/contentApi"

type ApiErr = {
  status?: number
  data?: { error?: { code?: string; message?: string }; message?: string }
}

function errorCode(err: unknown): string | undefined {
  const e = err as ApiErr
  return e?.data?.error?.code
}

function errorMessage(err: unknown): string {
  const e = err as ApiErr
  return (
    e?.data?.error?.message ||
    e?.data?.message ||
    "Could not update AI settings."
  )
}

function friendlyCode(code?: string): string | null {
  if (code === "BYOK_NOT_ALLOWED") {
    return "Your plan does not allow bring-your-own keys. Upgrade to Growth+."
  }
  if (code === "BYOK_KEYS_MISSING") {
    return "Add at least one OpenAI or Gemini key before enabling BYOK."
  }
  if (code === "QUOTA_EXCEEDED") {
    return "Monthly platform AI quota is used up. Upgrade or switch to BYOK."
  }
  return null
}

export function AiSettingsPage() {
  const { data, isLoading, error, refetch } = useGetAiSettingsQuery()
  const [put, putState] = usePutAiSettingsMutation()
  const [checkout, checkoutState] = useCreateCheckoutSessionMutation()
  const [portal, portalState] = useCreatePortalSessionMutation()

  const [mode, setMode] = useState<"platform" | "byok">("platform")
  const [openaiKey, setOpenaiKey] = useState("")
  const [geminiKey, setGeminiKey] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [savedMsg, setSavedMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return
    setMode(data.aiBillingMode === "byok" ? "byok" : "platform")
    setOpenaiKey("")
    setGeminiKey("")
  }, [data])

  const planLabel = useMemo(() => {
    const match = data?.plans.find((p) => p.id === data.planTier)
    return match?.label || data?.planTier || "ΓÇö"
  }, [data])

  const usagePct = useMemo(() => {
    if (!data) return 0
    const limit = Math.max(1, data.quota.monthlyLimit)
    return Math.min(100, (data.quota.usedThisMonth / limit) * 100)
  }, [data])

  const byokAllowed = Boolean(data?.byokAllowed)

  const upgrade = async (planTier = "growth") => {
    setFormError(null)
    try {
      const res = await checkout({ planTier }).unwrap()
      if (res.url) window.location.assign(res.url)
    } catch (err) {
      setFormError(friendlyCode(errorCode(err)) || errorMessage(err))
    }
  }

  const openPortal = async () => {
    setFormError(null)
    try {
      const res = await portal().unwrap()
      if (res.url) window.location.assign(res.url)
    } catch (err) {
      setFormError(friendlyCode(errorCode(err)) || errorMessage(err))
    }
  }

  const save = async (opts?: { clearOpenai?: boolean; clearGemini?: boolean }) => {
    setFormError(null)
    setSavedMsg(null)
    if (mode === "byok" && !byokAllowed) {
      setFormError(friendlyCode("BYOK_NOT_ALLOWED"))
      return
    }
    try {
      const body: {
        aiBillingMode: "platform" | "byok"
        openaiApiKey?: string
        geminiApiKey?: string
        clearOpenai?: boolean
        clearGemini?: boolean
      } = { aiBillingMode: mode }
      if (openaiKey.trim()) body.openaiApiKey = openaiKey.trim()
      if (geminiKey.trim()) body.geminiApiKey = geminiKey.trim()
      if (opts?.clearOpenai) body.clearOpenai = true
      if (opts?.clearGemini) body.clearGemini = true
      await put(body).unwrap()
      setOpenaiKey("")
      setGeminiKey("")
      setSavedMsg("AI settings saved.")
    } catch (err) {
      setFormError(friendlyCode(errorCode(err)) || errorMessage(err))
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">AI &amp; billing</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Choose platform-included AI or bring your own keys. Keys are stored securely and never shown
          again after save.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading AI settingsΓÇª</p>}
      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Could not load AI settings.
        </p>
      )}

      {(formError || putState.isError) && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {formError || friendlyCode(errorCode(putState.error)) || errorMessage(putState.error)}
        </p>
      )}
      {savedMsg && (
        <p className="rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
          {savedMsg}
        </p>
      )}

      {data && (
        <>
          <section className="glass-panel space-y-4 rounded-3xl p-5 shadow-elevated md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                  Current plan
                </p>
                <h2 className="font-display mt-1 text-xl">{planLabel}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Mode: {data.aiBillingMode}
                  {data.byokAllowed ? " ┬╖ BYOK available" : " ┬╖ BYOK locked on Starter"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  className="gap-2 rounded-xl"
                  disabled={checkoutState.isLoading}
                  onClick={() => void upgrade("growth")}
                >
                  <Sparkles className="h-4 w-4" />
                  {checkoutState.isLoading ? "StartingΓÇª" : "Upgrade"}
                </Button>
                <Button
                  variant="secondary"
                  className="gap-2 rounded-xl"
                  disabled={portalState.isLoading}
                  onClick={() => void openPortal()}
                >
                  <ExternalLink className="h-4 w-4" />
                  {portalState.isLoading ? "OpeningΓÇª" : "Billing portal"}
                </Button>
                <Button asChild variant="ghost" className="rounded-xl">
                  <Link to="/settings/billing">Full billing</Link>
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-muted/30 px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium">Platform AI quota</p>
                <p className="text-xs text-muted-foreground">{data.quota.month}</p>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {data.quota.usedThisMonth} used ┬╖ {data.quota.remaining} remaining ┬╖{" "}
                {data.quota.monthlyLimit} limit
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${usagePct}%` }}
                />
              </div>
              {data.aiBillingMode === "byok" && (
                <p className="mt-2 text-xs text-muted-foreground">
                  BYOK usage does not consume platform quota.
                </p>
              )}
            </div>
          </section>

          <section className="glass-panel space-y-4 rounded-3xl p-5 shadow-elevated md:p-6">
            <h2 className="font-display text-xl">AI mode</h2>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                className={`rounded-2xl border px-4 py-3 text-left transition ${
                  mode === "platform"
                    ? "border-primary/50 bg-primary/10"
                    : "border-border bg-card/40"
                }`}
                onClick={() => setMode("platform")}
              >
                <p className="text-sm font-semibold">Platform included AI</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  We pay model costs against your monthly quota.
                </p>
              </button>
              <button
                type="button"
                disabled={!byokAllowed}
                className={`rounded-2xl border px-4 py-3 text-left transition ${
                  mode === "byok"
                    ? "border-primary/50 bg-primary/10"
                    : "border-border bg-card/40"
                } ${!byokAllowed ? "cursor-not-allowed opacity-50" : ""}`}
                onClick={() => byokAllowed && setMode("byok")}
              >
                <p className="text-sm font-semibold">Bring your own keys</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {byokAllowed
                    ? "Your OpenAI/Gemini keys ΓÇö no platform AI COGS."
                    : "Upgrade to Growth+ to unlock BYOK."}
                </p>
              </button>
            </div>

            <div className={`space-y-4 ${!byokAllowed ? "opacity-60" : ""}`}>
              <div className="flex items-center gap-2 text-sm font-medium">
                <KeyRound className="h-4 w-4 text-primary" />
                BYOK keys
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor="openai-key">OpenAI API key</Label>
                    {data.keys.openaiConfigured && (
                      <span className="rounded-md bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary">
                        Configured
                      </span>
                    )}
                  </div>
                  <Input
                    id="openai-key"
                    type="password"
                    autoComplete="off"
                    placeholder={data.keys.openaiConfigured ? "ΓÇóΓÇóΓÇóΓÇóΓÇóΓÇóΓÇóΓÇó (leave blank to keep)" : "sk-ΓÇª"}
                    value={openaiKey}
                    disabled={!byokAllowed}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                  />
                  {data.keys.openaiConfigured && (
                    <button
                      type="button"
                      className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                      disabled={!byokAllowed || putState.isLoading}
                      onClick={() => void save({ clearOpenai: true })}
                    >
                      Clear OpenAI key
                    </button>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor="gemini-key">Gemini API key</Label>
                    {data.keys.geminiConfigured && (
                      <span className="rounded-md bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary">
                        Configured
                      </span>
                    )}
                  </div>
                  <Input
                    id="gemini-key"
                    type="password"
                    autoComplete="off"
                    placeholder={
                      data.keys.geminiConfigured ? "ΓÇóΓÇóΓÇóΓÇóΓÇóΓÇóΓÇóΓÇó (leave blank to keep)" : "AIzaΓÇª"
                    }
                    value={geminiKey}
                    disabled={!byokAllowed}
                    onChange={(e) => setGeminiKey(e.target.value)}
                  />
                  {data.keys.geminiConfigured && (
                    <button
                      type="button"
                      className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                      disabled={!byokAllowed || putState.isLoading}
                      onClick={() => void save({ clearGemini: true })}
                    >
                      Clear Gemini key
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                className="rounded-xl"
                disabled={putState.isLoading}
                onClick={() => void save()}
              >
                {putState.isLoading ? "SavingΓÇª" : "Save settings"}
              </Button>
              <button
                type="button"
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                onClick={() => void refetch()}
              >
                Refresh
              </button>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="font-display text-xl">Plans</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {data.plans.map((plan) => {
                const current = plan.id === data.planTier
                return (
                  <div
                    key={plan.id}
                    className={`rounded-2xl border p-4 ${
                      current ? "border-primary/50 bg-primary/5" : "border-border bg-card/40"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="font-display text-lg">{plan.label}</p>
                      <p className="text-sm font-semibold">${plan.monthlyUsd}/mo</p>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {plan.quota} AI posts/mo ┬╖ BYOK{" "}
                      {plan.byokAllowed ? "allowed" : "not included"}
                    </p>
                    <Button
                      size="sm"
                      variant={current ? "secondary" : "default"}
                      className="mt-3 gap-1.5 rounded-xl"
                      disabled={checkoutState.isLoading}
                      onClick={() => void upgrade(plan.id)}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      {current ? "Renew / change" : "Upgrade"}
                    </Button>
                  </div>
                )
              })}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
