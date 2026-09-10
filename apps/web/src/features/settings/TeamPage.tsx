import { useMemo, useState } from "react"
import { UserPlus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import {
  useCreateTenantInviteMutation,
  useListTenantInvitesQuery,
  useRevokeTenantInviteMutation,
} from "@/features/api/contentApi"

function apiError(err: unknown): string {
  const e = err as {
    data?: { error?: { message?: string; code?: string }; message?: string }
  }
  return e?.data?.error?.message || e?.data?.message || "Something went wrong"
}

export function TeamPage() {
  const { data, isLoading, error, refetch } = useListTenantInvitesQuery()
  const [createInvite, createState] = useCreateTenantInviteMutation()
  const [revokeInvite, revokeState] = useRevokeTenantInviteMutation()
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<"tenant_member" | "tenant_admin">("tenant_member")
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const pending = useMemo(
    () => (data?.invites || []).filter((i) => i.status === "pending"),
    [data],
  )
  const others = useMemo(
    () => (data?.invites || []).filter((i) => i.status !== "pending"),
    [data],
  )

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    setSuccess(null)
    try {
      const res = await createInvite({ email: email.trim(), role }).unwrap()
      setEmail("")
      setSuccess(
        res.emailSent
          ? `Invite sent to ${res.invite.email}.`
          : `Invite created for ${res.invite.email}. Email delivery is disabled locally — share the invite link from your mail provider once SES is enabled.`,
      )
    } catch (err) {
      setFormError(apiError(err))
    }
  }

  const revoke = async (inviteId: number) => {
    setFormError(null)
    try {
      await revokeInvite(inviteId).unwrap()
      setSuccess("Invite revoked.")
    } catch (err) {
      setFormError(apiError(err))
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">Team</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Invite teammates by email. They join your workspace with the role you choose.
        </p>
      </div>

      {(formError || createState.isError) && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {formError || apiError(createState.error)}
        </p>
      )}
      {success && (
        <p className="rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
          {success}
        </p>
      )}

      <section className="glass-panel space-y-4 rounded-3xl p-5 shadow-elevated md:p-6">
        <div className="flex items-center gap-2">
          <UserPlus className="h-4 w-4 text-primary" />
          <h2 className="font-display text-xl">Invite teammate</h2>
        </div>
        <form onSubmit={(e) => void submit(e)} className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="invite-email">Work email</Label>
            <Input
              id="invite-email"
              type="email"
              required
              autoComplete="email"
              placeholder="alex@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="invite-role">Role</Label>
            <select
              id="invite-role"
              className="h-11 sm:h-10 w-full rounded-xl border border-border bg-background/60 px-3 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value as "tenant_member" | "tenant_admin")}
            >
              <option value="tenant_member">Member</option>
              <option value="tenant_admin">Admin</option>
            </select>
          </div>
          <Button type="submit" className="rounded-xl h-11 sm:h-10" disabled={createState.isLoading}>
            {createState.isLoading ? "Sending…" : "Send invite"}
          </Button>
        </form>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-display text-xl">Pending invitations</h2>
          <button
            type="button"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void refetch()}
          >
            Refresh
          </button>
        </div>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {error && (
          <p className="text-sm text-destructive">Could not load invites. Tenant admin permission required.</p>
        )}
        {!isLoading && pending.length === 0 && (
          <p className="text-sm text-muted-foreground">No pending invites.</p>
        )}
        <ul className="space-y-2">
          {pending.map((inv) => (
            <li
              key={inv.inviteId}
              className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-border bg-card/40 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{inv.email}</p>
                <p className="text-xs text-muted-foreground">
                  {inv.role.replace("tenant_", "")} · expires{" "}
                  {inv.expiresAt ? new Date(inv.expiresAt).toLocaleString() : "—"}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="rounded-xl gap-1.5"
                disabled={revokeState.isLoading}
                onClick={() => void revoke(inv.inviteId)}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Revoke
              </Button>
            </li>
          ))}
        </ul>
      </section>

      {others.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-display text-lg">History</h2>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            {others.slice(0, 20).map((inv) => (
              <li key={inv.inviteId} className="flex justify-between gap-2 rounded-xl px-1 py-1">
                <span className="truncate">{inv.email}</span>
                <span className="shrink-0 capitalize">{inv.status}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
