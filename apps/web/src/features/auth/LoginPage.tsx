import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { useLoginMutation, useRegisterMutation } from "@/features/auth/authApi"
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
      // New tenants land in the agent workspace (primary product surface).
      navigate("/agent")
    } catch (err) {
      const msg = apiErrorMessage(err)
      if (msg) setFormError(msg)
    }
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
