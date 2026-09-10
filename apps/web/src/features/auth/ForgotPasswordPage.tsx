import { FormEvent, useState } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { useRequestPasswordResetMutation } from "@/features/auth/authApi"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [request, state] = useRequestPasswordResetMutation()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const res = await request({ email: email.trim() }).unwrap()
      setMessage(res.message)
    } catch (err) {
      setError(
        (err as { data?: { error?: { message?: string } } })?.data?.error?.message ||
          "Could not send reset email.",
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
          <h1 className="font-display text-3xl">Forgot password</h1>
          <p className="text-sm text-muted-foreground mt-1">
            We&apos;ll email a single-use reset link if an account exists.
          </p>
        </div>
        <div className="space-y-1">
          <Label>Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="text-sm text-primary" role="status">
            {message}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={state.isLoading}>
          Send reset link
        </Button>
        <Link to="/login" className="text-xs text-primary hover:underline">
          Back to login
        </Link>
      </motion.form>
    </div>
  )
}
