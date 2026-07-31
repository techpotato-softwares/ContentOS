import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useSelector } from "react-redux"
import type { RootState } from "@/app/store"
import {
  useLinkedInStatusQuery,
  useLinkedInConnectMutation,
  useLazyLinkedInOrganizationsQuery,
  useLinkedInSelectOrganizationMutation,
  useLinkedInDisconnectMutation,
  type LinkedInOrganization,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"

export function LinkedInPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const user = useSelector((s: RootState) => s.auth.user)
  const perms = useMemo(() => new Set(user?.permissions || []), [user?.permissions])
  const isAdmin =
    user?.roleName === "super_admin" ||
    perms.has("tenant:admin") ||
    perms.has("admin:tenants")

  const { data, refetch, isFetching } = useLinkedInStatusQuery()
  const [connect, connectState] = useLinkedInConnectMutation()
  const [loadOrgs, orgsState] = useLazyLinkedInOrganizationsQuery()
  const [selectOrg, selectState] = useLinkedInSelectOrganizationMutation()
  const [disconnect, disconnectState] = useLinkedInDisconnectMutation()
  const [orgs, setOrgs] = useState<LinkedInOrganization[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const member = data?.member
  const organization = data?.organization
  const showPicker =
    Boolean(organization?.pendingSelection) ||
    searchParams.get("linkedin") === "select_page"

  useEffect(() => {
    const flag = searchParams.get("linkedin")
    const code = searchParams.get("code")
    if (!flag) return
    if (flag === "connected") {
      setNotice("Personal LinkedIn connected.")
      void refetch()
    } else if (flag === "select_page") {
      setNotice("Select the company page to bind to this tenant.")
      void refetch()
      void loadOrgs()
        .unwrap()
        .then((res) => setOrgs(res.organizations || []))
        .catch(() =>
          setError(
            "Could not list company pages. Ensure Community Management API scopes are approved.",
          ),
        )
    } else if (flag === "error" && code === "LINKEDIN_ORG_SCOPES_UNAVAILABLE") {
      setError(
        "Company page OAuth failed — request Community Management API access on your LinkedIn app.",
      )
    }
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams, refetch, loadOrgs])

  useEffect(() => {
    if (organization?.pendingSelection) {
      void loadOrgs()
        .unwrap()
        .then((res) => setOrgs(res.organizations || []))
        .catch(() => undefined)
    }
  }, [organization?.pendingSelection, loadOrgs])

  const start = async (mode: "member" | "organization") => {
    setError(null)
    setNotice(null)
    try {
      const res = await connect({ mode }).unwrap()
      window.location.href = res.authorizeUrl
    } catch {
      setError(
        mode === "organization"
          ? "Could not start company page connect (admin only)."
          : "Could not start LinkedIn connect.",
      )
    }
  }

  const onSelect = async (org: LinkedInOrganization) => {
    setError(null)
    try {
      await selectOrg({
        organizationId: org.organizationId,
        name: org.name,
        vanityName: org.vanityName || undefined,
      }).unwrap()
      setNotice(`Connected company page: ${org.name}`)
      setOrgs([])
      void refetch()
    } catch {
      setError("Failed to bind company page.")
    }
  }

  const onDisconnect = async (kind: "member" | "organization") => {
    setError(null)
    try {
      await disconnect({ accountKind: kind }).unwrap()
      setNotice(kind === "member" ? "Personal profile disconnected." : "Company page disconnected.")
      void refetch()
    } catch {
      setError("Disconnect failed.")
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="font-display text-3xl">LinkedIn</h1>
        <p className="text-sm text-muted-foreground">
          Connect a personal profile for creators and a company page for B2B publishing.
        </p>
      </div>

      {notice && <p className="text-sm text-primary">{notice}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="rounded-2xl border border-border p-6 space-y-3 bg-background/40">
        <h2 className="font-display text-xl">Personal profile</h2>
        <p className="text-sm">
          Status:{" "}
          <strong>
            {member?.connected
              ? `Connected (${member.username || "member"})`
              : "Not connected"}
          </strong>
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => void start("member")}
            disabled={connectState.isLoading}
          >
            Connect personal
          </Button>
          {member?.connected && (
            <Button
              variant="outline"
              disabled={disconnectState.isLoading}
              onClick={() => void onDisconnect("member")}
            >
              Disconnect
            </Button>
          )}
          <Button variant="outline" onClick={() => void refetch()} disabled={isFetching}>
            Refresh
          </Button>
        </div>
      </div>

      {isAdmin && (
        <div className="rounded-2xl border border-border p-6 space-y-3 bg-background/40">
          <h2 className="font-display text-xl">Company page</h2>
          <p className="text-sm text-muted-foreground">
            Tenant admin / super admin only. Requires LinkedIn Community Management API.
          </p>
          <p className="text-sm">
            Status:{" "}
            <strong>
              {organization?.connected
                ? `Connected (${organization.username || "page"})`
                : organization?.pendingSelection
                  ? "Pending page selection"
                  : "Not connected"}
            </strong>
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => void start("organization")}
              disabled={connectState.isLoading}
            >
              Connect company page
            </Button>
            {(organization?.connected || organization?.pendingSelection) && (
              <Button
                variant="outline"
                disabled={disconnectState.isLoading}
                onClick={() => void onDisconnect("organization")}
              >
                Disconnect
              </Button>
            )}
            {organization?.pendingSelection && (
              <Button
                variant="secondary"
                disabled={orgsState.isFetching}
                onClick={() =>
                  void loadOrgs()
                    .unwrap()
                    .then((res) => setOrgs(res.organizations || []))
                }
              >
                Load pages
              </Button>
            )}
          </div>

          {(showPicker || orgs.length > 0) && (
            <div className="space-y-2 pt-2">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                Select a page
              </p>
              {orgsState.isFetching && (
                <p className="text-xs text-muted-foreground">Loading pages…</p>
              )}
              <ul className="space-y-2">
                {orgs.map((org) => (
                  <li
                    key={org.organizationId}
                    className="flex items-center justify-between gap-2 rounded-xl border border-border px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{org.name}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {org.vanityName || org.organizationId}
                        {org.role ? ` · ${org.role}` : ""}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      disabled={selectState.isLoading}
                      onClick={() => void onSelect(org)}
                    >
                      Use page
                    </Button>
                  </li>
                ))}
              </ul>
              {!orgsState.isFetching && orgs.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No postable pages found for this LinkedIn member.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
