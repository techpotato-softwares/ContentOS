import { useState } from "react"
import { Link } from "react-router-dom"
import { useAppSelector } from "@/app/hooks"
import { useRequestEmailVerificationMutation } from "@/features/auth/authApi"
import { Button } from "@/components/ui/button"

/** Soft-block banner: unverified users can use the app but cannot publish. */
export function EmailVerifyBanner() {
  const user = useAppSelector((s) => s.auth.user)
  const [request, state] = useRequestEmailVerificationMutation()
  const [note, setNote] = useState<string | null>(null)

  if (!user || user.emailVerified) return null

  const resend = async () => {
    if (!user.email) return
    try {
      const res = await request({ email: user.email }).unwrap()
      setNote(res.message)
    } catch {
      setNote("Could not send verification email. Try again later.")
    }
  }

  return (
    <div className="mb-4 rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium text-foreground">Verify your email to publish</p>
          <p className="text-muted-foreground mt-0.5">
            You can draft and review posts, but LinkedIn publishing stays locked until{" "}
            <span className="text-foreground">{user.email}</span> is verified.
          </p>
          {note && <p className="mt-1 text-primary">{note}</p>}
        </div>
        <div className="flex gap-2 shrink-0">
          <Button type="button" size="sm" variant="outline" onClick={() => void resend()} disabled={state.isLoading}>
            Resend link
          </Button>
          <Button type="button" size="sm" asChild>
            <Link to="/verify-email">Verify</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
