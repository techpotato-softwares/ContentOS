import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useExchangeGoogleCodeMutation } from "@/features/auth/authApi"
import { setSession } from "@/features/auth/authSlice"
import { useAppDispatch } from "@/app/hooks"

export function GoogleOAuthCallbackPage() {
  const [params] = useSearchParams()
  const [exchange] = useExchangeGoogleCodeMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code = params.get("code")
    if (!code) {
      setError("Missing Google sign-in code. Please try again.")
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const res = await exchange({ code }).unwrap()
        if (cancelled) return
        dispatch(
          setSession({
            accessToken: res.accessToken,
            refreshToken: res.refreshToken,
            user: res.user,
          }),
        )
        navigate("/agent", { replace: true })
      } catch (err) {
        if (cancelled) return
        const e = err as { data?: { error?: { message?: string } } }
        setError(
          e?.data?.error?.message ||
            "Google sign-in failed. Please try again from the login page.",
        )
      }
    })()
    return () => {
      cancelled = true
    }
  }, [params, exchange, dispatch, navigate])

  return (
    <div className="min-h-dvh flex items-center justify-center p-6">
      <div className="glass-panel max-w-md w-full rounded-3xl p-8 space-y-4 text-center">
        <h1 className="font-display text-2xl">Signing you in…</h1>
        {error ? (
          <>
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
            <Link to="/login" className="text-sm text-primary underline">
              Back to login
            </Link>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Completing Google authentication…
          </p>
        )}
      </div>
    </div>
  )
}
