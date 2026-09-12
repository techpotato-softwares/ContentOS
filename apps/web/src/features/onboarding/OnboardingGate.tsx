import { useEffect, useRef } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { useAppSelector } from "@/app/hooks"
import { useGetOnboardingQuery } from "@/features/api/contentApi"

/**
 * Soft gate: after login/session restore, send incomplete tenants to /onboarding once.
 * Never re-forces skipped/completed tenants. Does not block navigating to real features.
 */
export function OnboardingGate() {
  const token = useAppSelector((s) => s.auth.accessToken)
  const navigate = useNavigate()
  const location = useLocation()
  const redirected = useRef(false)
  const { data, isSuccess } = useGetOnboardingQuery(undefined, { skip: !token })

  useEffect(() => {
    if (!token || !isSuccess || !data || redirected.current) return
    if (!data.showWizard) return
    if (location.pathname === "/onboarding") {
      redirected.current = true
      return
    }
    // Only auto-redirect from default home surfaces, not mid-feature deep links
    const homeSurfaces = new Set(["/", "/dashboard", "/agent"])
    if (!homeSurfaces.has(location.pathname)) return
    redirected.current = true
    navigate("/onboarding", { replace: true })
  }, [token, isSuccess, data, location.pathname, navigate])

  return null
}
