import { Navigate, Route, Routes } from "react-router-dom"
import { useAppSelector } from "@/app/hooks"
import { AppShell } from "@/shared/layout/AppShell"
import { InstallPrompt } from "@/shared/pwa/InstallPrompt"
import { LoginPage } from "@/features/auth/LoginPage"
import { GoogleOAuthCallbackPage } from "@/features/auth/GoogleOAuthCallbackPage"
import { DashboardPage } from "@/features/dashboard/DashboardPage"
import { AgentPage } from "@/features/agent/AgentPage"
import { ReviewPage } from "@/features/posts/ReviewPage"
import { TrainingPage } from "@/features/training/TrainingPage"
import { TeamPage } from "@/features/settings/TeamPage"
import { AcceptInvitePage } from "@/features/settings/AcceptInvitePage"
import { AdminTenantsPage } from "@/features/tenants/AdminTenantsPage"
import { LinkedInPage } from "@/features/social/LinkedInPage"
import { InsightsPage } from "@/features/insights/InsightsPage"
import { AnalyticsPage } from "@/features/insights/AnalyticsPage"
import { OnboardingPage } from "@/features/onboarding/OnboardingPage"
import { OnboardingGate } from "@/features/onboarding/OnboardingGate"

function Protected({ children }: { children: React.ReactNode }) {
  const token = useAppSelector((s) => s.auth.accessToken)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function AppRouter() {
  return (
    <>
      <InstallPrompt />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/login/oauth/callback" element={<GoogleOAuthCallbackPage />} />
        <Route path="/invite/accept" element={<AcceptInvitePage />} />
        <Route
          path="/"
          element={
            <Protected>
              <OnboardingGate />
              <AppShell />
            </Protected>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="agent" element={<AgentPage />} />
          <Route path="insights" element={<InsightsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="settings/training" element={<TrainingPage />} />
          <Route path="settings/team" element={<TeamPage />} />
          <Route path="connections/linkedin" element={<LinkedInPage />} />
          <Route path="admin/tenants" element={<AdminTenantsPage />} />
          <Route
            path="admin/tenants/:id/training"
            element={<TrainingPage />}
          />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  )
}
