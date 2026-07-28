import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { useLoginMutation, useRegisterMutation } from "@/features/auth/authApi"
import { setSession } from "@/features/auth/authSlice"
import { useAppDispatch } from "@/app/hooks"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [email, setEmail] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [login, loginState] = useLoginMutation()
  const [register, registerState] = useRegisterMutation()
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const error =
    (loginState.error as { data?: { error?: { message?: string } } })?.data?.error?.message ||
    (registerState.error as { data?: { error?: { message?: string } } })?.data?.error?.message

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res =
        mode === "login"
          ? await login({ username, password }).unwrap()
          : await register({ username, email, password, companyName }).unwrap()
      dispatch(
        setSession({
          accessToken: res.accessToken,
          refreshToken: res.refreshToken,
          user: res.user,
        }),
      )
      navigate("/dashboard")
    } catch {
      /* shown via error */
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <motion.form
        onSubmit={submit}
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-panel w-full max-w-md rounded-3xl p-8 space-y-5"
      >
        <div>
          <h1 className="font-display text-3xl">ContentOS</h1>
          <p className="text-sm text-muted-foreground mt-1">
            B2B LinkedIn image posts with company-consistent context
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={mode === "login" ? "default" : "outline"}
            className="flex-1"
            onClick={() => setMode("login")}
          >
            Login
          </Button>
          <Button
            type="button"
            variant={mode === "register" ? "default" : "outline"}
            className="flex-1"
            onClick={() => setMode("register")}
          >
            Register company
          </Button>
        </div>
        {mode === "register" && (
          <>
            <div className="space-y-1">
              <Label>Company name</Label>
              <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
            </div>
            <div className="space-y-1">
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
          </>
        )}
        <div className="space-y-1">
          <Label>Username</Label>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label>Password</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={loginState.isLoading || registerState.isLoading}>
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Seed users: <code>superadmin</code> / <code>demo</code> — password{" "}
          <code>ChangeMe123!</code>
        </p>
        <Link to="/" className="text-xs text-primary">
          Home
        </Link>
      </motion.form>
    </div>
  )
}
