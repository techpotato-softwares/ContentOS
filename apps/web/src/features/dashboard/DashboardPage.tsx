import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import {
  ArrowUpRight,
  BarChart3,
  Bot,
  ClipboardCheck,
  Lightbulb,
  Palette,
  Sparkles,
  ImageIcon,
  Send,
  Layers,
} from "lucide-react"
import { useAppSelector } from "@/app/hooks"
import { useListPostsQuery, useGetOnboardingQuery } from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { DashboardOrb } from "@/shared/ui/DashboardOrb"
import { mediaSrc } from "@/shared/lib/media"
import { cn } from "@/shared/lib/utils"

const actions = [
  {
    to: "/agent",
    title: "Chat & generate",
    desc: "Briefs → 3 branded LinkedIn variants",
    icon: Bot,
    tone: "from-teal-500/20 to-cyan-500/5",
  },
  {
    to: "/insights",
    title: "Insights",
    desc: "Domain suggestions & industry news",
    icon: Lightbulb,
    tone: "from-emerald-500/20 to-teal-500/5",
  },
  {
    to: "/analytics",
    title: "Analytics",
    desc: "Reach metrics & publish timing",
    icon: BarChart3,
    tone: "from-cyan-500/20 to-sky-500/5",
  },
  {
    to: "/review",
    title: "Review queue",
    desc: "Approve before LinkedIn publish",
    icon: ClipboardCheck,
    tone: "from-teal-600/20 to-emerald-500/5",
  },
  {
    to: "/settings/training",
    title: "Company training",
    desc: "Brand, domain & contact footer",
    icon: Palette,
    tone: "from-primary/25 to-secondary/10",
  },
]

export function DashboardPage() {
  const user = useAppSelector((s) => s.auth.user)
  const brand = useAppSelector((s) => s.theme.brand)
  const { data: posts = [] } = useListPostsQuery()
  const { data: onboarding } = useGetOnboardingQuery()

  const drafts = posts.filter((p) => p.status === "draft").length
  const pending = posts.filter((p) => p.status === "pending_review").length
  const approved = posts.filter((p) => p.status === "approved").length
  const published = posts.filter((p) => p.status === "published").length
  const recent = posts.slice(0, 6)

  const stats = [
    { label: "Drafts", value: drafts, icon: Layers },
    { label: "In review", value: pending, icon: ClipboardCheck },
    { label: "Ready", value: approved, icon: ImageIcon },
    { label: "Published", value: published, icon: Send },
  ]

  return (
    <div className="space-y-8">
      {onboarding?.showWizard && (
        <section className="rounded-3xl border border-primary/30 bg-primary/8 p-4 md:p-5 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="font-medium">Finish workspace setup</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Connect LinkedIn, train your brand, generate, review, and publish.
            </p>
          </div>
          <Button asChild className="rounded-xl shrink-0">
            <Link to="/onboarding">
              Continue setup
              <ArrowUpRight className="h-4 w-4" />
            </Link>
          </Button>
        </section>
      )}
      <section className="relative overflow-hidden rounded-3xl border border-border bg-linear-to-br from-primary/10 via-background/40 to-secondary/15 p-6 md:p-8">
        <div className="pointer-events-none absolute -right-8 top-0 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
        <div className="pointer-events-none absolute -left-10 bottom-0 h-48 w-48 rounded-full bg-primary/15 blur-3xl" />
        <div className="relative grid lg:grid-cols-[1.2fr_0.8fr] gap-6 items-center">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary mb-4">
              <Sparkles className="h-3.5 w-3.5" />
              LinkedIn content automation
            </div>
            <h1 className="font-display text-3xl sm:text-4xl md:text-5xl leading-tight">
              Welcome back, {user?.username}
            </h1>
            <p className="text-muted-foreground mt-3 max-w-xl text-sm sm:text-base">
              Create on-brand informative posts for{" "}
              <span className="text-foreground font-medium">
                {brand?.appDisplayName || "your company"}
              </span>
              , review them, and publish for reach — without starting from a blank page.
            </p>
            <div className="flex flex-col sm:flex-row flex-wrap gap-3 mt-6 w-full">
              <Button asChild className="w-full sm:w-auto">
                <Link to="/agent">
                  Generate posts
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full sm:w-auto">
                <Link to="/insights">Browse insights</Link>
              </Button>
            </div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="relative h-60 md:h-70 rounded-2xl border border-border/60 bg-background/30 backdrop-blur-sm overflow-hidden"
          >
            <DashboardOrb className="absolute inset-0" />
            <div className="absolute bottom-3 left-3 right-3 flex justify-between text-[11px] text-muted-foreground">
              <span>Brand engine</span>
              <span className="text-primary">Live</span>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {stats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            className="rounded-2xl border border-border bg-card/60 backdrop-blur-sm p-4 flex items-center gap-3"
          >
            <div className="h-11 w-11 rounded-xl bg-primary/15 text-primary flex items-center justify-center">
              <s.icon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{s.label}</div>
              <div className="font-display text-2xl leading-none mt-0.5">{s.value}</div>
            </div>
          </motion.div>
        ))}
      </section>

      <section>
        <div className="flex items-end justify-between mb-4">
          <div>
            <h2 className="font-display text-2xl">Workspace</h2>
            <p className="text-sm text-muted-foreground">Jump into the next step of your content loop</p>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {actions.map((c, i) => (
            <motion.div
              key={c.to}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 * i }}
              className={cn(
                "group relative overflow-hidden rounded-2xl border border-border p-5 bg-linear-to-br",
                c.tone,
              )}
            >
              <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-primary/10 blur-2xl group-hover:bg-primary/20 transition-colors" />
              <div className="relative flex items-start gap-3">
                <div className="h-11 w-11 rounded-xl bg-background/70 border border-border flex items-center justify-center text-primary shadow-sm">
                  <c.icon className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-display text-xl">{c.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1 mb-4">{c.desc}</p>
                  <Button asChild size="sm" variant="secondary">
                    <Link to={c.to}>
                      Open
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-display text-2xl">Recent creatives</h2>
            <p className="text-sm text-muted-foreground">Latest generated LinkedIn image posts</p>
          </div>
          <Button asChild size="sm" variant="outline">
            <Link to="/review">View all</Link>
          </Button>
        </div>
        {recent.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border p-10 text-center">
            <ImageIcon className="h-8 w-8 mx-auto text-primary/70 mb-3" />
            <p className="text-sm text-muted-foreground mb-4">No posts yet — generate your first batch.</p>
            <Button asChild size="sm">
              <Link to="/agent">Start generating</Link>
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {recent.map((p, i) => {
              const src = mediaSrc(p.imageUrl)
              return (
                <motion.div
                  key={p.postId}
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.04 * i }}
                  className="rounded-xl border border-border overflow-hidden bg-background/50"
                >
                  {src ? (
                    <img src={src} alt="" className="aspect-square w-full object-cover" />
                  ) : (
                    <div className="aspect-square bg-muted flex items-center justify-center">
                      <ImageIcon className="h-6 w-6 text-muted-foreground" />
                    </div>
                  )}
                  <div className="p-2">
                    <div className="text-[10px] uppercase tracking-wide text-primary truncate">{p.angle}</div>
                    <div className="text-[10px] text-muted-foreground">{p.status}</div>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
