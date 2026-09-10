import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useAppDispatch, useAppSelector } from "@/app/hooks"
import { setSession } from "@/features/auth/authSlice"
import { useLoginMutation } from "@/features/auth/authApi"
import {
  useAcceptTenantInviteMutation,
  usePreviewTenantInviteQuery,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

function apiError(err: unknown): string {
  const e = err as {
    data?: { error?: { message?: string; code?: string }; message?: string }
  }
  return e?.data?.error?.message || e?.data?.message || "Could not accept invite"
}

export function AcceptInvitePage() {
  const [params] = useSearchParams()
  const token = (params.get("token") || "").trim()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const sessionUser = useAppSelector((s) => s.auth.user)
  const accessToken = useAppSelector((s) => s.auth.accessToken)

  const preview = usePreviewTenantInviteQuery(token, { skip: !token })
  const [accept, acceptState] = useAcceptTenantInviteMutation()
  const [login, loginState] = useLoginMutation()

  const [mode, setMode] = useState<"register" | "login">("register")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (preview.data?.email) setEmail(preview.data.email)
  }, [preview.data?.email])

  const heading = useMemo(() => {
    if (!preview.data) return "Accept invite"
    return `Join ${preview.data.tenantName || "workspace"}`
  }, [preview.data])

  const finish = (res: {
    accessToken: string
    refreshToken: string
    user: {
      userId: number
      username: string
      email?: string
      roleName?: string | null
      tenantId?: number | null
      permissions?: string[]
      modulesEnabled?: string[]
    }
  }) => {
    dispatch(
      setSession({
        accessToken: res.accessToken,
        refreshToken: res.refreshToken,
        user: {
          userId: res.user.userId,
          username: res.user.username,
          email: res.user.email,
          roleName: res.user.roleName,
          tenantId: res.user.tenantId,
          permissions: res.user.permissions,
          modulesEnabled: res.user.modulesEnabled,
        },
      }),
    )
    navigate("/agent")
  }

  const acceptAuthenticated = async () => {
    setFormError(null)
    try {
      const res = await accept({ token }).unwrap()
      finish(res)
    } catch (err) {
      setFormError(apiError(err))
    }
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    try {
      if (mode === "login") {
        const logged = await login({ username, password }).unwrap()
        dispatch(
          setSession({
            accessToken: logged.accessToken,
            refreshToken: logged.refreshToken,
            user: logged.user,
          }),
        )
        const res = await accept({ token }).unwrap()
        finish(res)
        return
      }
      const res = await accept({
        token,
        username,
        email: email.trim() || preview.data?.email,
        password,
      }).unwrap()
      finish(res)
    } catch (err) {
      setFormError(apiError(err))
    }
  }

  if (!token) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-6">
        <h1 className="font-display text-2xl">Invalid invite</h1>
        <p className="text-sm text-muted-foreground">This link is missing an invite token.</p>
        <Button asChild className="rounded-xl">
          <Link to="/login">Go to login</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="min-h-dvh flex items-center justify-center p-4">
      <div className="w-full max-w-md glass-panel rounded-3xl p-6 shadow-elevated space-y-5">
        <div>
          <h1 className="font-display text-2xl">{heading}</h1>
          {preview.isLoading && (
            <p className="mt-2 text-sm text-muted-foreground">Loading invite…</p>
          )}
          {preview.error && (
            <p className="mt-2 text-sm text-destructive">{apiError(preview.error)}</p>
          )}
          {preview.data && (
            <p className="mt-2 text-sm text-muted-foreground">
              Invited as <strong>{preview.data.role.replace("tenant_", "")}</strong> for{" "}
              <strong>{preview.data.email}</strong>
            </p>
          )}
        </div>

        {(formError || acceptState.error) && (
          <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {formError || apiError(acceptState.error)}
          </p>
        )}

        {accessToken && sessionUser ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Signed in as <strong>{sessionUser.email || sessionUser.username}</strong>
            </p>
            <Button
              className="w-full rounded-xl"
              disabled={acceptState.isLoading}
              onClick={() => void acceptAuthenticated()}
            >
              {acceptState.isLoading ? "Joining…" : "Accept invite"}
            </Button>
          </div>
        ) : (
          <form className="space-y-3" onSubmit={(e) => void submit(e)}>
            <div className="grid grid-cols-2 gap-2">
              <Button
                type="button"
                variant={mode === "register" ? "default" : "outline"}
                className="rounded-xl"
                onClick={() => setMode("register")}
              >
                Create account
              </Button>
              <Button
                type="button"
                variant={mode === "login" ? "default" : "outline"}
                className="rounded-xl"
                onClick={() => setMode("login")}
              >
                Sign in
              </Button>
            </div>
            {mode === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="inv-email">Email</Label>
                <Input
                  id="inv-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="inv-user">Username</Label>
              <Input
                id="inv-user"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="inv-pass">Password</Label>
              <Input
                id="inv-pass"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button
              type="submit"
              className="w-full rounded-xl"
              disabled={acceptState.isLoading || loginState.isLoading}
            >
              {acceptState.isLoading || loginState.isLoading
                ? "Working…"
                : mode === "register"
                  ? "Create account & join"
                  : "Sign in & join"}
            </Button>
          </form>
        )}

        <p className="text-center text-xs text-muted-foreground">
          <Link to="/login" className="underline-offset-2 hover:underline">
            Back to login
          </Link>
        </p>
      </div>
    </div>
  )
}
