import { FormEvent, useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { useAcceptInviteMutation } from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

type Status = "idle" | "loading" | "success" | "invalid" | "expired" | "revoked" | "used" | "error"

function classifyError(err: unknown): Status {
  const code = (err as { data?: { error?: { code?: string } } })?.data?.error?.code
  if (code === "INVITE_EXPIRED") return "expired"
  if (code === "INVITE_REVOKED") return "revoked"
  if (code === "INVITE_USED") return "used"
  if (code === "INVALID_INVITE") return "invalid"
  return "error"
}

export function AcceptInvitePage() {
  const [params] = useSearchParams()
  const token = useMemo(() => params.get("token") || "", [params])
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [status, setStatus] = useState<Status>(token ? "idle" : "invalid")
  const [message, setMessage] = useState<string | null>(
    token ? null : "Open the invite link from your email to continue.",
  )
  const [accept, state] = useAcceptInviteMutation()
  const navigate = useNavigate()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!token) {
      setStatus("invalid")
      setMessage("Missing invite token.")
      return
    }
    setStatus("loading")
    try {
      const res = await accept({ token, username: username.trim(), password }).unwrap()
      setStatus("success")
      setMessage(res.message || "Invite accepted. You can sign in.")
      setTimeout(() => navigate("/login"), 1200)
    } catch (err) {
      const s = classifyError(err)
      setStatus(s)
      setMessage(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          "Could not accept invite.",
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
          <h1 className="font-display text-3xl">Accept invite</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create your account to join the team.
          </p>
        </div>
        {token && status !== "success" && (
          <>
            <div className="space-y-1">
              <Label>Username</Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
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
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={state.isLoading || status === "loading"}>
              Join team
            </Button>
          </>
        )}
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
        <Link to="/login" className="text-xs text-primary hover:underline">
          Back to login
        </Link>
      </motion.form>
    </div>
  )
}
