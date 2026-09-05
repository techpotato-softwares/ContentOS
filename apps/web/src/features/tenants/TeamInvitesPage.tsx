import { FormEvent, useState } from "react"
import {
  useCreateInviteMutation,
  useListInvitesQuery,
  useRevokeInviteMutation,
} from "@/features/api/contentApi"
import { useAppSelector } from "@/app/hooks"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { Navigate } from "react-router-dom"

const ROLES = [
  { value: "tenant_member", label: "Member" },
  { value: "tenant_admin", label: "Admin" },
] as const

export function TeamInvitesPage() {
  const user = useAppSelector((s) => s.auth.user)
  const canManage =
    user?.roleName === "super_admin" ||
    user?.permissions?.includes("tenant:admin") ||
    user?.permissions?.includes("admin:tenants")

  const { data: invites = [], isLoading, refetch } = useListInvitesQuery(undefined, {
    skip: !canManage,
  })
  const [create, createState] = useCreateInviteMutation()
  const [revoke, revokeState] = useRevokeInviteMutation()
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<string>("tenant_member")
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [devLink, setDevLink] = useState<string | null>(null)

  if (!canManage) {
    return <Navigate to="/dashboard" replace />
  }

  const onInvite = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setMessage(null)
    setDevLink(null)
    try {
      const res = await create({ email: email.trim(), role }).unwrap()
      setMessage(`Invite sent to ${res.email} as ${res.role}.`)
      if (res.devLink) setDevLink(res.devLink)
      setEmail("")
      void refetch()
    } catch (err) {
      setError(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          "Could not create invite.",
      )
    }
  }

  const onRevoke = async (id: number) => {
    setError(null)
    try {
      await revoke(id).unwrap()
      setMessage("Invite revoked.")
      void refetch()
    } catch (err) {
      setError(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          "Could not revoke invite.",
      )
    }
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="font-display text-3xl">Team</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Invite teammates by email. They join your company with the role you assign.
        </p>
      </div>

      <form onSubmit={onInvite} className="space-y-4 rounded-2xl border border-border p-5 bg-background/40">
        <h2 className="font-medium">Invite teammate</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1 sm:col-span-2">
            <Label>Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="space-y-1">
            <Label>Role</Label>
            <select
              className="flex h-10 w-full rounded-xl border border-input bg-background px-3 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <Button type="submit" disabled={createState.isLoading}>
          Send invite
        </Button>
      </form>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="text-sm text-primary" role="status">
          {message}
        </p>
      )}
      {devLink && (
        <p className="text-xs text-muted-foreground break-all">
          Local accept link:{" "}
          <a className="text-primary underline" href={devLink}>
            {devLink}
          </a>
        </p>
      )}

      <div className="space-y-3">
        <h2 className="font-medium">Pending invites</h2>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && invites.length === 0 && (
          <p className="text-sm text-muted-foreground">No pending invites.</p>
        )}
        <ul className="space-y-2">
          {invites.map((inv) => (
            <li
              key={inv.inviteId}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-3 bg-background/40"
            >
              <div>
                <div className="font-medium text-sm">{inv.email}</div>
                <div className="text-xs text-muted-foreground">
                  {inv.role}
                  {inv.expiresAt ? ` · expires ${new Date(inv.expiresAt).toLocaleString()}` : ""}
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={revokeState.isLoading}
                onClick={() => void onRevoke(inv.inviteId)}
              >
                Revoke
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
