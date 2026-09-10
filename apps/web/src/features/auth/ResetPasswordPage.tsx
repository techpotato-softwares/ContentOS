import { FormEvent, useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { useConfirmPasswordResetMutation } from "@/features/auth/authApi"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

type Status = "idle" | "loading" | "success" | "invalid" | "expired" | "used" | "error"

function classifyError(err: unknown): Status {
  const code = (err as { data?: { error?: { code?: string } } })?.data?.error?.code
  if (code === "TOKEN_EXPIRED") return "expired"
  if (code === "TOKEN_USED") return "used"
  if (code === "INVALID_TOKEN") return "invalid"
  return "error"
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = useMemo(() => params.get("token") || "", [params])
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [status, setStatus] = useState<Status>("idle")
  const [message, setMessage] = useState<string | null>(
    token ? null : "Open the reset link from your email to continue.",
  )
  const [reset, state] = useConfirmPasswordResetMutation()
  const navigate = useNavigate()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!token) {
      setStatus("invalid")
      setMessage("Missing reset token.")
      return
    }
    if (password.length < 8) {
      setStatus("error")
      setMessage("Password must be at least 8 characters.")
      return
    }
    if (password !== confirm) {
      setStatus("error")
      setMessage("Passwords do not match.")
      return
    }
    setStatus("loading")
    try {
      const res = await reset({ token, password }).unwrap()
      setStatus("success")
      setMessage(res.message)
      setTimeout(() => navigate("/login"), 1200)
    } catch (err) {
      const s = classifyError(err)
      setStatus(s)
      setMessage(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          "Could not reset password.",
      )
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <motion.form
        onSubmit={onSubmit}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-md rounded-3xl p-8 space-y-5"
      >
        <div>
          <h1 className="font-display text-3xl">Reset password</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Choose a new password. Existing sessions will be signed out.
          </p>
        </div>
        {token ? (
          <>
            <div className="space-y-1">
              <Label>New password</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-1">
              <Label>Confirm password</Label>
              <Input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={state.isLoading || status === "loading"}>
              Update password
            </Button>
          </>
        ) : null}
        {message && (
          <p
            className={
              status === "success" ? "text-sm text-primary" : "text-sm text-muted-foreground"
            }
            role="status"
          >
            {message}
          </p>
        )}
        <div className="flex gap-3 text-xs">
          <Link to="/login" className="text-primary hover:underline">
            Back to login
          </Link>
          <Link to="/forgot-password" className="text-primary hover:underline">
            Request a new link
          </Link>
        </div>
      </motion.form>
    </div>
  )
}
