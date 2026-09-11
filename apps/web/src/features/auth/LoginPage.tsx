import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { AnimatePresence, motion } from "framer-motion"
import { useLoginMutation, useRegisterMutation } from "@/features/auth/authApi"
import { setSession } from "@/features/auth/authSlice"
import { useAppDispatch } from "@/app/hooks"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"
import { cn } from "@/shared/lib/utils"

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

function marketingHomeUrl(): string {
  const base = (import.meta.env.VITE_MARKETING_URL as string | undefined)?.replace(/\/$/, "")
  return base || "/"
}

const proofs = [
  "Brand-trained drafts — not generic AI",
  "Human approval before every publish",
  "Workspace ready the moment you sign up",
]

const steps = [
  { n: "01", label: "Train" },
  { n: "02", label: "Generate" },
  { n: "03", label: "Approve" },
  { n: "04", label: "Publish" },
]

export function LoginPage() {
  const [searchParams] = useSearchParams()
  const initialMode =
    searchParams.get("mode") === "register" || searchParams.get("signup") === "1"
      ? "register"
      : "login"
  const [mode, setMode] = useState<"login" | "register">(initialMode)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [email, setEmail] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [login, loginState] = useLoginMutation()
  const [register, registerState] = useRegisterMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  useEffect(() => {
    if (searchParams.get("mode") === "register" || searchParams.get("signup") === "1") {
      setMode("register")
    }
  }, [searchParams])

  const error =
    formError ||
    apiErrorMessage(loginState.error) ||
    apiErrorMessage(registerState.error)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    if (mode === "register" && !companyName.trim()) {
      setFormError("Company name is required.")
      return
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

  const busy = loginState.isLoading || registerState.isLoading
  const isRegister = mode === "register"

  return (
    <div className="auth-stage relative min-h-dvh overflow-hidden text-[#e8f5f2]">
      <div className="auth-lights" aria-hidden>
        <span className="auth-light auth-light-a" />
        <span className="auth-light auth-light-b" />
        <span className="auth-light auth-light-c" />
        <span className="auth-light auth-light-d" />
        <span className="auth-beam" />
        <span className="auth-beam auth-beam-b" />
        <span className="auth-pulse-ring" />
        <span className="auth-pulse-ring auth-pulse-ring-b" />
        <div className="auth-grid absolute inset-0" />
      </div>

      <div className="relative z-1 mx-auto grid min-h-dvh max-w-6xl lg:grid-cols-[1.05fr_0.95fr]">
        {/* Brand stage */}
        <motion.aside
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex flex-col justify-between px-6 pb-2 pt-8 sm:px-10 lg:px-12 lg:py-12"
        >
          <div>
            <a
              href={marketingHomeUrl()}
              className="font-display inline-flex items-baseline text-[1.65rem] tracking-tight text-[#f2faf6] transition hover:opacity-85"
            >
              Content<span className="text-[#3ee9c9]">OS</span>
            </a>

            <div className="mt-8 flex flex-wrap gap-2 lg:mt-14">
              <span className="auth-chip">
                <span className="h-1.5 w-1.5 rounded-full bg-[#3ee9c9]" />
                LinkedIn content OS
              </span>
              <span className="auth-chip">Free to start</span>
            </div>

            <AnimatePresence mode="wait">
              <motion.h1
                key={mode}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.28 }}
                className="font-display mt-6 max-w-[16ch] text-[2.35rem] leading-[1.05] tracking-tight text-[#f2faf6] sm:text-5xl lg:text-[3.35rem]"
              >
                {isRegister ? (
                  <>
                    Start free.
                    <span className="mt-1 block text-[#3ee9c9]">Ship on-brand.</span>
                  </>
                ) : (
                  <>
                    Welcome back
                    <span className="mt-1 block text-[#3ee9c9]">to ContentOS.</span>
                  </>
                )}
              </motion.h1>
            </AnimatePresence>

            <p className="mt-5 max-w-sm text-[0.95rem] leading-relaxed text-[#8ba69c] sm:text-base">
              Train once. Generate drafts. Approve every post before it goes live.
            </p>

            <ul className="mt-8 hidden space-y-3 lg:block">
              {proofs.map((item, i) => (
                <motion.li
                  key={item}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.18 + i * 0.06, duration: 0.35 }}
                  className="flex items-start gap-3 text-sm text-[#c5dbd2]"
                >
                  <span className="mt-1.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[#3ee9c9]/40 bg-[#0f3a32]/60">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#3ee9c9]" />
                  </span>
                  {item}
                </motion.li>
              ))}
            </ul>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.45 }}
            className="auth-preview mt-10 hidden overflow-hidden rounded-2xl p-4 lg:block"
          >
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#8ba69c]">
                Weekly loop
              </p>
              <span className="rounded-full border border-[#3ee9c9]/30 bg-[#0f3a32]/70 px-2 py-0.5 text-[10px] font-semibold text-[#3ee9c9]">
                Live
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {steps.map((step) => (
                <div
                  key={step.n}
                  className="rounded-xl border border-white/8 bg-white/3 px-2 py-3 text-center"
                >
                  <p className="font-display text-lg text-[#3ee9c9]">{step.n}</p>
                  <p className="mt-1 text-[11px] font-medium text-[#c5dbd2]">{step.label}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-[#8ba69c]">
              Free to start · No credit card · Human approval always on
            </p>
          </motion.div>
        </motion.aside>

        {/* Form stage */}
        <div className="flex items-center justify-center px-4 pb-10 pt-2 sm:px-8 lg:px-10 lg:py-12">
          <div className="auth-form-stage relative w-full max-w-105">
            <div className="auth-form-rounds" aria-hidden>
              <span className="auth-form-round auth-form-round-a" />
              <span className="auth-form-round auth-form-round-b" />
              <span className="auth-form-round auth-form-round-c" />
              <span className="auth-form-glow" />
            </div>
            <motion.form
              onSubmit={submit}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
              className="auth-panel relative z-1 w-full space-y-5 rounded-[1.6rem] p-5 sm:p-8"
            >
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#3ee9c9]">
                {isRegister ? "Start free" : "Sign in"}
              </p>
              <h2 className="font-display mt-2 text-[1.65rem] leading-tight text-[#f2faf6]">
                {isRegister ? "Create your workspace" : "Log in to continue"}
              </h2>
              <p className="mt-1.5 text-sm text-[#8ba69c]">
                {isRegister
                  ? "Self-serve signup — your company tenant is ready instantly."
                  : "Use your username or work email."}
              </p>
            </div>

            <div className="auth-mode" role="tablist" aria-label="Auth mode">
              {(["login", "register"] as const).map((m) => {
                const active = mode === m
                return (
                  <button
                    key={m}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className={cn("auth-mode-btn", active && "is-active")}
                    onClick={() => {
                      setMode(m)
                      setFormError(null)
                    }}
                  >
                    {active && (
                      <motion.span
                        layoutId="auth-mode-pill"
                        className="auth-mode-pill"
                        transition={{ type: "spring", stiffness: 420, damping: 34 }}
                      />
                    )}
                    <span className="relative z-1">
                      {m === "login" ? "Login" : "Start free"}
                    </span>
                  </button>
                )
              })}
            </div>

            <AnimatePresence mode="wait" initial={false}>
              {isRegister && (
                <motion.div
                  key="register-fields"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                  className="space-y-4 overflow-hidden"
                >
                  <div className="space-y-1.5">
                    <Label htmlFor="company" className="text-[#c5dbd2]">
                      Company name
                    </Label>
                    <Input
                      id="company"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="Acme Cloud"
                      required={isRegister}
                      autoComplete="organization"
                      className="auth-field"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="email" className="text-[#c5dbd2]">
                      Work email
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.com"
                      required={isRegister}
                      autoComplete="email"
                      className="auth-field"
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-1.5">
              <Label htmlFor="username" className="text-[#c5dbd2]">
                Username
              </Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={isRegister ? "choose a username" : "username or email"}
                required
                autoComplete="username"
                className="auth-field"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-[#c5dbd2]">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  className="auth-field pr-12"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-xs font-medium text-[#8ba69c] transition hover:text-[#3ee9c9]"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <motion.p
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border border-red-400/25 bg-red-500/10 px-3 py-2.5 text-sm text-red-300"
                role="alert"
              >
                {error}
              </motion.p>
            )}

            <Button
              type="submit"
              className="auth-submit h-12 w-full rounded-xl text-[0.95rem]"
              size="lg"
              disabled={busy}
            >
              {busy
                ? isRegister
                  ? "Creating workspace…"
                  : "Signing in…"
                : isRegister
                  ? "Create free account"
                  : "Sign in"}
            </Button>

            <p className="text-center text-xs text-[#8ba69c]">
              {isRegister ? (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    className="font-semibold text-[#3ee9c9] underline-offset-2 hover:underline"
                    onClick={() => {
                      setMode("login")
                      setFormError(null)
                    }}
                  >
                    Sign in
                  </button>
                </>
              ) : (
                <>
                  New here?{" "}
                  <button
                    type="button"
                    className="font-semibold text-[#3ee9c9] underline-offset-2 hover:underline"
                    onClick={() => {
                      setMode("register")
                      setFormError(null)
                    }}
                  >
                    Start free
                  </button>
                </>
              )}
            </p>
          </motion.form>
          </div>
        </div>
      </div>
    </div>
  )
}
