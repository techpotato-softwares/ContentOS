import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  googleOAuthStartUrl,
  linkedinOidcStartUrl,
  useLoginMutation,
  useRegisterMutation,
} from "@/features/auth/authApi"
import { setSession } from "@/features/auth/authSlice"
import { useAppDispatch } from "@/app/hooks"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

function apiErrorMessage(err: unknown): string | undefined {
  if (!err || typeof err !== "object") return undefined
  const e = err as {
    status?: number | string
    data?: { error?: { message?: string; code?: string }; message?: string }
  }
  const msg = e.data?.error?.message || e.data?.message
  if (msg) return msg
  if (e.status === 409) {
    return "An account with this email already exists. Sign in or use a different email."
  }
  if (e.status === 400) {
    return "Please check the form and try again."
  }
  return undefined
}

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [login, loginState] = useLoginMutation()
  const [register, registerState] = useRegisterMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const oauthError = searchParams.get("oauthError")
    const oauthMessage = searchParams.get("oauthMessage")
    if (oauthError || oauthMessage) {
      setFormError(
        oauthMessage ||
          "Sign-in failed. If this email already belongs to another account, use password login or the original provider.",
      )
    }
  }, [searchParams])

  const error =
    formError ||
    apiErrorMessage(loginState.error) ||
    apiErrorMessage(registerState.error)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    if (mode === "register") {
      if (!companyName.trim()) {
        setFormError("Company name is required.")
        return
      }
      if (!email.trim()) {
        setFormError("Work email is required.")
        return
      }
    }
    try {
      const res =
        mode === "login"
          ? await login({ username, password }).unwrap()
          : await register({
              username,
              email: email.trim(),
              password,
              companyName: companyName.trim(),
            }).unwrap()
      dispatch(
        setSession({
          accessToken: res.accessToken,
          refreshToken: res.refreshToken,
          user: res.user,
        }),
      )
      navigate("/agent")
    } catch (err) {
      const msg = apiErrorMessage(err)
      if (msg) setFormError(msg)
    }
  }

  const continueWithGoogle = () => {
    window.location.assign(googleOAuthStartUrl())
  }

  const continueWithLinkedIn = () => {
    window.location.assign(linkedinOidcStartUrl())
  }

  return (
    <div className="min-h-dvh flex items-center justify-center p-4 sm:p-6">
      <motion.form
        onSubmit={submit}
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-panel w-full max-w-md rounded-3xl p-5 sm:p-8 space-y-5"
      >
        <div>
          <h1 className="font-display text-2xl sm:text-3xl">ContentOS</h1>
          <p className="text-sm text-muted-foreground mt-1">
            B2B LinkedIn image posts with company-consistent context
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={mode === "login" ? "default" : "outline"}
            className="flex-1"
            onClick={() => {
              setMode("login")
              setFormError(null)
            }}
          >
            Login
          </Button>
          <Button
            type="button"
            variant={mode === "register" ? "default" : "outline"}
            className="flex-1"
            onClick={() => {
              setMode("register")
              setFormError(null)
            }}
          >
            Register company
          </Button>
        </div>

        <Button
          type="button"
          variant="outline"
          className="w-full gap-2"
          onClick={continueWithGoogle}
        >
          <svg aria-hidden className="h-4 w-4" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continue with Google
        </Button>

        <Button
          type="button"
          variant="outline"
          className="w-full gap-2"
          onClick={continueWithLinkedIn}
        >
          <svg aria-hidden className="h-4 w-4" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"
            />
          </svg>
          Continue with LinkedIn
        </Button>

        <div className="relative text-center text-xs text-muted-foreground">
          <span className="bg-card px-2 relative z-10">or continue with email</span>
          <div className="absolute inset-x-0 top-1/2 border-t border-border" />
        </div>

        {mode === "register" && (
          <>
            <div className="space-y-1">
              <Label>Company name</Label>
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Cloud"
                required
                autoComplete="organization"
              />
            </div>
            <div className="space-y-1">
              <Label>Work email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
          </>
        )}
        <div className="space-y-1">
          <Label>Username</Label>
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
          />
        </div>
        <div className="space-y-1">
          <Label>Password</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </div>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        <Button
          type="submit"
          className="w-full"
          disabled={loginState.isLoading || registerState.isLoading}
        >
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Self-serve signup creates your company workspace automatically. Local seed
          users (<code>superadmin</code> / <code>demo</code>) are for development only.
        </p>
        <Link to="/" className="text-xs text-primary">
          Home
        </Link>
      </motion.form>
    </div>
  )
}
