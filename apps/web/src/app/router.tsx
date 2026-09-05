import { Navigate, Route, Routes } from "react-router-dom"
import { useAppSelector } from "@/app/hooks"
import { AppShell } from "@/shared/layout/AppShell"
import { LoginPage } from "@/features/auth/LoginPage"
import { DashboardPage } from "@/features/dashboard/DashboardPage"
import { AgentPage } from "@/features/agent/AgentPage"
import { ReviewPage } from "@/features/posts/ReviewPage"
import { TrainingPage } from "@/features/training/TrainingPage"
import { AdminTenantsPage } from "@/features/tenants/AdminTenantsPage"
import { TeamInvitesPage } from "@/features/tenants/TeamInvitesPage"
import { AcceptInvitePage } from "@/features/tenants/AcceptInvitePage"
import { LinkedInPage } from "@/features/social/LinkedInPage"
import { InsightsPage } from "@/features/insights/InsightsPage"
import { AnalyticsPage } from "@/features/insights/AnalyticsPage"

function Protected({ children }: { children: React.ReactNode }) {
  const token = useAppSelector((s) => s.auth.accessToken)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route
        path="/"
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="agent" element={<AgentPage />} />
        <Route path="insights" element={<InsightsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="settings/training" element={<TrainingPage />} />
        <Route path="settings/team" element={<TeamInvitesPage />} />
        <Route path="connections/linkedin" element={<LinkedInPage />} />
        <Route path="admin/tenants" element={<AdminTenantsPage />} />
        <Route path="admin/tenants/:id/training" element={<TrainingPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
