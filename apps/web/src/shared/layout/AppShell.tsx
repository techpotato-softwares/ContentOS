import { NavLink, Outlet, useLocation } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
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
  MoreHorizontal,
  Users,
  Cpu,
  CreditCard,
  type LucideIcon,
} from "lucide-react"
import { useAppDispatch, useAppSelector } from "@/app/hooks"
import { logout } from "@/features/auth/authSlice"
import { setColorMode, setBrand } from "@/app/theme/themeSlice"
import { useGetThemeQuery, type ThemePayload } from "@/features/api/contentApi"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/shared/lib/utils"

type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  admin?: boolean
}

const links: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agent", label: "Agent", icon: Bot },
  { to: "/insights", label: "Insights", icon: Lightbulb },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/review", label: "Review", icon: ClipboardCheck },
  { to: "/connections/linkedin", label: "LinkedIn", icon: Share2 },
  { to: "/settings/training", label: "Training", icon: Palette },
  { to: "/settings/ai", label: "AI", icon: Cpu },
  { to: "/settings/billing", label: "Billing", icon: CreditCard },
  { to: "/settings/team", label: "Team", icon: Users },
  { to: "/admin/tenants", label: "Tenants", icon: Building2, admin: true },
]

const primaryTabPaths = new Set(["/dashboard", "/agent", "/insights", "/review"])

function BrandMark({
  brand,
  title,
  compact,
}: {
  brand: ThemePayload | null | undefined
  title: string
  compact?: boolean
}) {
  return (
    <div className={cn("flex items-center gap-3 min-w-0", compact ? "px-0" : "px-2")}>
      {brand?.logoUrl ? (
        <img
          src={brand.logoUrl}
          alt=""
          className={cn(
            "rounded-xl object-cover ring-2 ring-primary/30 shrink-0",
            compact ? "h-9 w-9" : "h-10 w-10",
          )}
        />
      ) : (
        <div
          className={cn(
            "rounded-xl bg-linear-to-br from-primary to-secondary flex items-center justify-center font-display text-primary-foreground font-semibold shadow-glow shrink-0",
            compact ? "h-9 w-9 text-sm" : "h-10 w-10",
          )}
        >
          C
        </div>
      )}
      <div className="min-w-0">
        <div className={cn("font-display leading-tight truncate", compact ? "text-base" : "text-lg")}>
          {title}
        </div>
        {!compact && (
          <div className="text-[11px] text-muted-foreground">
            {brand?.source === "tenant" ? "Client brand" : "Platform theme"}
          </div>
        )}
      </div>
    </div>
  )
}

function SidebarNavLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200 shrink-0",
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
            <item.icon className="h-4 w-4" />
          </span>
          {item.label}
        </>
      )}
    </NavLink>
  )
}

export function AppShell() {
  const dispatch = useAppDispatch()
  const location = useLocation()
  const user = useAppSelector((s) => s.auth.user)
  const colorMode = useAppSelector((s) => s.theme.colorMode)
  const brand = useAppSelector((s) => s.theme.brand)
  const { data: theme } = useGetThemeQuery(undefined, { skip: !user })
  const isWorkspace = location.pathname === "/agent"
  const [moreOpen, setMoreOpen] = useState(false)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", colorMode === "dark")
  }, [colorMode])

  useEffect(() => {
    if (theme) dispatch(setBrand(theme))
  }, [theme, dispatch])

  useEffect(() => {
    setMoreOpen(false)
  }, [location.pathname])

  const isAdmin =
    user?.roleName === "super_admin" || user?.permissions?.includes("admin:tenants")
  const title = brand?.appDisplayName || "ContentOS"
  const visibleLinks = links.filter((l) => !l.admin || isAdmin)
  const primaryTabs = visibleLinks.filter((l) => primaryTabPaths.has(l.to))
  const moreLinks = visibleLinks.filter((l) => !primaryTabPaths.has(l.to))
  const moreActive = moreLinks.some(
    (l) => location.pathname === l.to || location.pathname.startsWith(`${l.to}/`),
  )

  const toggleTheme = () =>
    dispatch(setColorMode(colorMode === "dark" ? "light" : "dark"))

  return (
    <div
      className={cn(
        "flex relative",
        isWorkspace ? "h-dvh overflow-hidden" : "min-h-dvh",
      )}
    >
      <div className="pointer-events-none absolute inset-0 mesh-bg" aria-hidden />

      {/* Desktop sidebar */}
      <aside className="hidden md:flex glass-panel z-10 w-64 m-3 mr-0 rounded-3xl p-4 flex-col gap-4 shadow-elevated shrink-0 h-[calc(100dvh-1.5rem)] sticky top-3 overflow-hidden">
        <BrandMark brand={brand} title={title} />
        <nav className="flex flex-col gap-1 flex-1 min-h-0 overflow-y-auto pr-0.5 -mr-0.5">
          {visibleLinks.map((l) => (
            <SidebarNavLink key={l.to} item={l} />
          ))}
        </nav>
        <div className="mt-auto shrink-0 flex items-center gap-2 pt-3 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            className="rounded-xl h-10 w-10 shrink-0 px-0"
            title={colorMode === "dark" ? "Light mode" : "Dark mode"}
            aria-label={colorMode === "dark" ? "Light mode" : "Dark mode"}
            onClick={toggleTheme}
          >
            {colorMode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="flex-1 rounded-xl h-10 hover:bg-muted/80 gap-2 min-w-0"
            title={`Logout · ${user?.username || ""}`}
            onClick={() => dispatch(logout())}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            <span className="truncate">{user?.username}</span>
          </Button>
        </div>
      </aside>

      <div
        className={cn(
          "relative z-10 flex-1 min-w-0 flex flex-col",
          isWorkspace && "min-h-0",
        )}
      >
        {/* Mobile top bar */}
        <header
          className={cn(
            "md:hidden glass-panel mx-3 mt-3 rounded-2xl px-3 py-2.5 flex items-center gap-2 shadow-elevated shrink-0",
            "pt-[max(0.625rem,env(safe-area-inset-top))]",
          )}
        >
          <BrandMark brand={brand} title={title} compact />
          <div className="ml-auto flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="rounded-xl h-11 w-11 shrink-0 px-0"
              title={colorMode === "dark" ? "Light mode" : "Dark mode"}
              aria-label={colorMode === "dark" ? "Light mode" : "Dark mode"}
              onClick={toggleTheme}
            >
              {colorMode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="rounded-xl h-11 w-11 shrink-0 px-0"
              title={`Logout · ${user?.username || ""}`}
              aria-label="Logout"
              onClick={() => dispatch(logout())}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <main
          className={cn(
            "relative flex-1 p-2.5 sm:p-3 min-w-0",
            "pb-[calc(4.75rem+env(safe-area-inset-bottom))] md:pb-3",
            isWorkspace && "min-h-0 flex flex-col",
          )}
        >
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className={cn(
              "glass-panel rounded-3xl p-3 sm:p-4 md:p-6 shadow-elevated",
              isWorkspace
                ? "flex-1 min-h-0 overflow-hidden flex flex-col md:h-[calc(100dvh-1.5rem)]"
                : "min-h-0 md:min-h-[calc(100dvh-1.5rem)] overflow-visible",
            )}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      {/* Mobile bottom tabs */}
      <nav
        className={cn(
          "md:hidden fixed inset-x-0 bottom-0 z-30 glass-panel border-t border-border rounded-none",
          "pb-[env(safe-area-inset-bottom)]",
        )}
        aria-label="Primary"
      >
        <div className="flex items-stretch justify-around gap-0.5 px-1 pt-1.5 pb-1.5">
          {primaryTabs.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                cn(
                  "flex flex-1 flex-col items-center justify-center gap-0.5 rounded-xl py-2 min-h-11 text-[10px] font-medium transition-colors",
                  isActive ? "text-primary" : "text-muted-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <l.icon className={cn("h-5 w-5", isActive && "text-primary")} />
                  <span className="truncate max-w-18">{l.label}</span>
                </>
              )}
            </NavLink>
          ))}
          <button
            type="button"
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-0.5 rounded-xl py-2 min-h-11 text-[10px] font-medium transition-colors",
              moreOpen || moreActive ? "text-primary" : "text-muted-foreground",
            )}
            aria-expanded={moreOpen}
            aria-controls="mobile-more-sheet"
            onClick={() => setMoreOpen((o) => !o)}
          >
            <MoreHorizontal className="h-5 w-5" />
            <span>More</span>
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {moreOpen && (
          <>
            <motion.button
              type="button"
              aria-label="Close more menu"
              className="md:hidden fixed inset-0 z-40 bg-black/40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMoreOpen(false)}
            />
            <motion.div
              id="mobile-more-sheet"
              role="dialog"
              aria-modal="true"
              aria-label="More navigation"
              className="md:hidden fixed inset-x-0 bottom-0 z-50 glass-panel rounded-t-3xl border-t border-border shadow-elevated px-4 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))]"
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 320 }}
            >
              <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-muted-foreground/30" />
              <p className="text-xs text-muted-foreground mb-2 px-1">More</p>
              <div className="flex flex-col gap-1">
                {moreLinks.map((l) => (
                  <NavLink
                    key={l.to}
                    to={l.to}
                    onClick={() => setMoreOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-3 rounded-2xl px-3 py-3 text-sm min-h-11",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted/80",
                      )
                    }
                  >
                    <l.icon className="h-5 w-5 shrink-0" />
                    {l.label}
                  </NavLink>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
