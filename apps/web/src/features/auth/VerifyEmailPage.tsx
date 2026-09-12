import { FormEvent, useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  useConfirmEmailVerificationMutation,
  useRequestEmailVerificationMutation,
} from "@/features/auth/authApi"
import { setSession } from "@/features/auth/authSlice"
import { useAppDispatch } from "@/app/hooks"
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

function messageFor(status: Status) {
  switch (status) {
    case "success":
      return "Email verified. You can publish LinkedIn posts."
    case "expired":
      return "This verification link has expired. Request a new one below."
    case "used":
      return "This verification link was already used."
    case "invalid":
      return "This verification link is invalid."
    default:
      return "Something went wrong. Try again."
  }
}

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = useMemo(() => params.get("token") || "", [params])
  const [email, setEmail] = useState("")
  const [status, setStatus] = useState<Status>("idle")
  const [message, setMessage] = useState<string | null>(null)
  const [confirm, confirmState] = useConfirmEmailVerificationMutation()
  const [request, requestState] = useRequestEmailVerificationMutation()
  const dispatch = useAppDispatch()

  const runConfirm = async (value: string) => {
    setStatus("loading")
    try {
      const res = await confirm({ token: value }).unwrap()
      if (res.accessToken && res.refreshToken && res.user) {
        dispatch(
          setSession({
            accessToken: res.accessToken,
            refreshToken: res.refreshToken,
            user: res.user,
          }),
        )
      }
      setStatus("success")
      setMessage(res.message || messageFor("success"))
    } catch (err) {
      const s = classifyError(err)
      setStatus(s)
      setMessage(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          messageFor(s),
      )
    }
  }

  useEffect(() => {
    if (token) void runConfirm(token)
    else {
      setMessage(
        "Enter your email to resend a verification link, or open the link from your inbox.",
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const onResend = async (e: FormEvent) => {
    e.preventDefault()
    setStatus("loading")
    try {
      const res = await request({ email: email.trim() }).unwrap()
      setStatus("success")
      setMessage(res.message)
    } catch (err) {
      setStatus("error")
      setMessage(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          "Could not send verification email.",
      )
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-md rounded-3xl p-8 space-y-5"
      >
        <h1 className="font-display text-3xl">Verify email</h1>
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
        {(confirmState.isLoading || status === "loading") && (
          <p className="text-sm text-muted-foreground">Working…</p>
        )}
        {token && status !== "success" && status !== "loading" && (
          <Button type="button" onClick={() => void runConfirm(token)} className="w-full">
            Retry verification
          </Button>
        )}
        {(status === "expired" || status === "invalid" || !token) && (
          <form onSubmit={onResend} className="space-y-3">
            <div className="space-y-1">
              <Label>Work email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={requestState.isLoading}>
              Send verification link
            </Button>
          </form>
        )}
        <div className="flex gap-3 text-xs">
          <Link to="/login" className="text-primary hover:underline">
            Back to login
          </Link>
          {status === "success" && (
            <Link to="/agent" className="text-primary hover:underline">
              Open agent
            </Link>
          )}
        </div>
      </motion.div>
    </div>
  )
}
