import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import {
  useLoginMutation,
  useRegisterMutation,
  useRequestOtpMutation,
  useVerifyOtpMutation,
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
  if (e.status === 429) {
    return "Too many attempts. Please wait a moment and try again."
  }
  if (e.status === 404) {
    return "No account found for this email. Register first or check the address."
  }
  if (e.status === 400) {
    return "Please check the form and try again."
  }
  return undefined
}

type AuthMode = "login" | "register"
type LoginMethod = "password" | "otp"
type OtpStep = "email" | "code"

export function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login")
  const [loginMethod, setLoginMethod] = useState<LoginMethod>("password")
  const [otpStep, setOtpStep] = useState<OtpStep>("email")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [otpCode, setOtpCode] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [otpInfo, setOtpInfo] = useState<string | null>(null)
  const [login, loginState] = useLoginMutation()
  const [register, registerState] = useRegisterMutation()
  const [requestOtp, requestOtpState] = useRequestOtpMutation()
  const [verifyOtp, verifyOtpState] = useVerifyOtpMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const busy =
    loginState.isLoading ||
    registerState.isLoading ||
    requestOtpState.isLoading ||
    verifyOtpState.isLoading

  const error =
    formError ||
    apiErrorMessage(loginState.error) ||
    apiErrorMessage(registerState.error) ||
    apiErrorMessage(requestOtpState.error) ||
    apiErrorMessage(verifyOtpState.error)

  const applySession = (res: {
    accessToken: string
    refreshToken: string
    user: import("./authSlice").AuthUser
  }) => {
    dispatch(
      setSession({
        accessToken: res.accessToken,
        refreshToken: res.refreshToken,
        user: res.user,
      }),
    )
    navigate("/agent")
  }

  const sendOtp = async () => {
    setFormError(null)
    setOtpInfo(null)
    const normalized = email.trim().toLowerCase()
    if (!normalized || !normalized.includes("@")) {
      setFormError("Enter a valid work email.")
      return
    }
    try {
      const res = await requestOtp({ email: normalized }).unwrap()
      setEmail(res.email || normalized)
      setOtpStep("code")
      setOtpCode("")
      setOtpInfo(
        res.inboxUrl
          ? `${res.message || "Code sent."} Open mailbox: ${res.inboxUrl}`
          : res.message || "Check your email for a sign-in code.",
      )
    } catch (err) {
      const msg = apiErrorMessage(err)
      if (msg) setFormError(msg)
    }
  }

  const submitPasswordOrRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    setOtpInfo(null)
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
      applySession(res)
    } catch (err) {
      const msg = apiErrorMessage(err)
      if (msg) setFormError(msg)
    }
  }

  const submitRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    await sendOtp()
  }

  const submitVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    const code = otpCode.trim()
    if (!/^\d{4,8}$/.test(code)) {
      setFormError("Enter the numeric code from your email.")
      return
    }
    try {
      const res = await verifyOtp({ email: email.trim().toLowerCase(), code }).unwrap()
      applySession(res)
    } catch (err) {
      const msg = apiErrorMessage(err)
      if (msg) setFormError(msg)
    }
  }

  const resetToLoginPassword = () => {
    setMode("login")
    setLoginMethod("password")
    setOtpStep("email")
    setFormError(null)
    setOtpInfo(null)
  }

  return (
    <div className="min-h-dvh flex items-center justify-center p-4 sm:p-6">
      <motion.div
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
            onClick={resetToLoginPassword}
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
              setOtpInfo(null)
            }}
          >
            Register company
          </Button>
        </div>

        {mode === "login" && (
          <div className="flex gap-2 rounded-xl border border-border p-1">
            <Button
              type="button"
              size="sm"
              variant={loginMethod === "password" ? "default" : "ghost"}
              className="flex-1"
              onClick={() => {
                setLoginMethod("password")
                setFormError(null)
                setOtpInfo(null)
              }}
            >
              Password
            </Button>
            <Button
              type="button"
              size="sm"
              variant={loginMethod === "otp" ? "default" : "ghost"}
              className="flex-1"
              onClick={() => {
                setLoginMethod("otp")
                setOtpStep("email")
                setFormError(null)
                setOtpInfo(null)
              }}
            >
              Email OTP
            </Button>
          </div>
        )}

        {mode === "register" && (
          <form onSubmit={submitPasswordOrRegister} className="space-y-5">
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
                autoComplete="new-password"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              Create account
            </Button>
          </form>
        )}

        {mode === "login" && loginMethod === "password" && (
          <form onSubmit={submitPasswordOrRegister} className="space-y-5">
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
                autoComplete="current-password"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              Sign in
            </Button>
          </form>
        )}

        {mode === "login" && loginMethod === "otp" && otpStep === "email" && (
          <form onSubmit={submitRequestOtp} className="space-y-5">
            <div className="space-y-1">
              <Label>Work email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@company.com"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {requestOtpState.isLoading ? "Sending…" : "Send sign-in code"}
            </Button>
          </form>
        )}

        {mode === "login" && loginMethod === "otp" && otpStep === "code" && (
          <form onSubmit={submitVerifyOtp} className="space-y-5">
            <p className="text-sm text-muted-foreground">
              Code sent to <span className="text-foreground font-medium">{email}</span>
            </p>
            {otpInfo && (
              <p className="text-sm text-muted-foreground" role="status">
                {otpInfo.includes("http://") ? (
                  <>
                    {otpInfo.split("Open mailbox:")[0]}
                    <a
                      className="text-primary underline underline-offset-2"
                      href={otpInfo.match(/https?:\/\/\S+/)?.[0]}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open local mailbox
                    </a>
                  </>
                ) : (
                  otpInfo
                )}
              </p>
            )}
            <div className="space-y-1">
              <Label>Sign-in code</Label>
              <Input
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="one-time-code"
                value={otpCode}
                onChange={(e) =>
                  setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 8))
                }
                required
                placeholder="6-digit code"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {verifyOtpState.isLoading ? "Verifying…" : "Verify & sign in"}
            </Button>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                disabled={busy}
                onClick={() => {
                  setOtpStep("email")
                  setOtpCode("")
                  setFormError(null)
                  setOtpInfo(null)
                }}
              >
                Change email
              </Button>
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                disabled={busy}
                onClick={() => void sendOtp()}
              >
                Resend code
              </Button>
            </div>
          </form>
        )}

        <p className="text-xs text-muted-foreground">
          Self-serve signup creates your company workspace automatically. Local seed
          users (<code>superadmin</code> / <code>demo</code>) are for development only.
        </p>
        <Link to="/" className="text-xs text-primary">
          Home
        </Link>
      </motion.div>
    </div>
  )
}
