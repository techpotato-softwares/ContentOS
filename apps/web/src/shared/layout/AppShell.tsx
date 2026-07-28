import { NavLink, Outlet } from "react-router-dom"
import { motion } from "framer-motion"
import {
  Bot,
  Building2,
  LayoutDashboard,
  LogOut,
  Moon,
  Sun,
  Share2,
  ClipboardCheck,
  Palette,
  Lightbulb,
  BarChart3,
} from "lucide-react"
import { useAppDispatch, useAppSelector } from "@/app/hooks"
import { logout } from "@/features/auth/authSlice"
import { setColorMode, setBrand } from "@/app/theme/themeSlice"
import { useGetThemeQuery } from "@/features/api/contentApi"
import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/shared/lib/utils"

const links = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agent", label: "Agent", icon: Bot },
  { to: "/insights", label: "Insights", icon: Lightbulb },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/review", label: "Review", icon: ClipboardCheck },
  { to: "/connections/linkedin", label: "LinkedIn", icon: Share2 },
  { to: "/settings/training", label: "Training", icon: Palette },
  { to: "/admin/tenants", label: "Tenants", icon: Building2, admin: true },
]

export function AppShell() {
  const dispatch = useAppDispatch()
  const user = useAppSelector((s) => s.auth.user)
  const colorMode = useAppSelector((s) => s.theme.colorMode)
  const brand = useAppSelector((s) => s.theme.brand)
  const { data: theme } = useGetThemeQuery(undefined, { skip: !user })

  useEffect(() => {
    document.documentElement.classList.toggle("dark", colorMode === "dark")
  }, [colorMode])

  useEffect(() => {
    if (theme) dispatch(setBrand(theme))
  }, [theme, dispatch])

  const isAdmin = user?.roleName === "super_admin" || user?.permissions?.includes("admin:tenants")
  const title = brand?.appDisplayName || "ContentOS"

  return (
    <div className="min-h-screen flex relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 mesh-bg" aria-hidden />
      <aside className="glass-panel relative z-10 w-64 m-3 mr-0 rounded-3xl p-4 flex flex-col gap-6 shadow-elevated">
        <div className="flex items-center gap-3 px-2">
          {brand?.logoUrl ? (
            <img src={brand.logoUrl} alt="" className="h-10 w-10 rounded-xl object-cover ring-2 ring-primary/30" />
          ) : (
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center font-display text-primary-foreground font-semibold shadow-glow">
              C
            </div>
          )}
          <div>
            <div className="font-display text-lg leading-tight">{title}</div>
            <div className="text-[11px] text-muted-foreground">
              {brand?.source === "tenant" ? "Client brand" : "Platform theme"}
            </div>
          </div>
        </div>
        <nav className="flex flex-col gap-1 flex-1">
          {links
            .filter((l) => !l.admin || isAdmin)
            .map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-glow"
                      : "hover:bg-muted/80 text-foreground/90",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "h-8 w-8 rounded-xl flex items-center justify-center transition-colors",
                        isActive ? "bg-black/10" : "bg-primary/10 text-primary group-hover:bg-primary/15",
                      )}
                    >
                      <l.icon className="h-4 w-4" />
                    </span>
                    {l.label}
                  </>
                )}
              </NavLink>
            ))}
        </nav>
        <div className="flex items-center gap-2 pt-2 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            className="rounded-xl"
            onClick={() => dispatch(setColorMode(colorMode === "dark" ? "light" : "dark"))}
          >
            {colorMode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="sm" className="flex-1 rounded-xl" onClick={() => dispatch(logout())}>
            <LogOut className="h-4 w-4" />
            <span className="truncate">{user?.username}</span>
          </Button>
        </div>
      </aside>
      <main className="relative z-10 flex-1 p-3 min-w-0">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="glass-panel min-h-[calc(100vh-1.5rem)] rounded-3xl p-6 md:p-8 shadow-elevated"
        >
          <Outlet />
        </motion.div>
      </main>
    </div>
  )
}
