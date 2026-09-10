import { useMemo } from "react"
import { CreditCard, ExternalLink, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  useGetBillingSummaryQuery,
  useCreateCheckoutSessionMutation,
  useCreatePortalSessionMutation,
} from "@/features/api/contentApi"

export function BillingPage() {
  const { data, isLoading, error, refetch } = useGetBillingSummaryQuery()
  const [checkout, checkoutState] = useCreateCheckoutSessionMutation()
  const [portal, portalState] = useCreatePortalSessionMutation()

  const statusLabel = useMemo(() => {
    const s = data?.billingStatus || "none"
    if (s === "active" || s === "trialing") return "Active"
    if (s === "past_due" || s === "unpaid") return "Payment required"
    if (s === "canceled") return "Canceled"
    return "No subscription"
  }, [data?.billingStatus])

  const needsBillingAttention =
    data &&
    !data.byok &&
    ["past_due", "unpaid", "canceled", "incomplete_expired"].includes(data.billingStatus)

  const startCheckout = async (planTier: string) => {
    const res = await checkout({ planTier }).unwrap()
    if (res.url) window.location.assign(res.url)
  }

  const openPortal = async () => {
    const res = await portal().unwrap()
    if (res.url) window.location.assign(res.url)
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">Billing</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Upgrade your plan or manage Stripe billing. Razorpay (INR) is a separate gateway.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading billing…</p>}
      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Could not load billing summary.
        </p>
      )}

      {data && (
        <>
          {needsBillingAttention && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
              Platform AI is paused until payment is updated. BYOK mode is not affected.
            </div>
          )}

          <section className="glass-panel rounded-3xl p-5 md:p-6 space-y-4 shadow-elevated">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                  Current plan
                </p>
                <h2 className="font-display mt-1 text-xl">{data.planLabel}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  ${data.monthlyUsd}/mo · Status: {statusLabel} · Mode: {data.aiBillingMode}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.hasStripeCustomer ? (
                  <Button
                    onClick={() => void openPortal()}
                    disabled={portalState.isLoading}
                    className="rounded-xl gap-2"
                  >
                    <CreditCard className="h-4 w-4" />
                    {portalState.isLoading ? "Opening…" : "Manage billing"}
                  </Button>
                ) : (
                  <Button
                    onClick={() => void startCheckout(data.planTier || "starter")}
                    disabled={checkoutState.isLoading}
                    className="rounded-xl gap-2"
                  >
                    <Sparkles className="h-4 w-4" />
                    {checkoutState.isLoading ? "Starting…" : "Upgrade / subscribe"}
                  </Button>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-muted/30 px-4 py-3">
              <p className="text-sm font-medium">Platform AI quota</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {data.quota.used} / {data.quota.limit} posts
                {data.quota.month ? ` · ${data.quota.month}` : ""}
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{
                    width: `${Math.min(100, (data.quota.used / Math.max(1, data.quota.limit)) * 100)}%`,
                  }}
                />
              </div>
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
                      {plan.quota} AI posts/mo · BYOK {plan.byokAllowed ? "allowed" : "not included"}
                    </p>
                    <Button
                      size="sm"
                      variant={current ? "secondary" : "default"}
                      className="mt-3 rounded-xl gap-1.5"
                      disabled={checkoutState.isLoading}
                      onClick={() => void startCheckout(plan.id)}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      {current ? "Renew / change" : "Upgrade"}
                    </Button>
                  </div>
                )
              })}
            </div>
            <button
              type="button"
              className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void refetch()}
            >
              Refresh billing status
            </button>
          </section>
        </>
      )}
    </div>
  )
}
