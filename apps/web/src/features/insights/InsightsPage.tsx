import { useState } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { useGetSuggestionsQuery, useGetIndustryNewsQuery } from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"

type Tab = "suggestions" | "news"

export function InsightsPage() {
  const [tab, setTab] = useState<Tab>("suggestions")
  const suggestions = useGetSuggestionsQuery(undefined, { skip: tab !== "suggestions" })
  const news = useGetIndustryNewsQuery(undefined, { skip: tab !== "news" })

  const tabs: { id: Tab; label: string }[] = [
    { id: "suggestions", label: "Suggestions" },
    { id: "news", label: "Industry news" },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl">Content insights</h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Domain-aware ideas from company training and industry briefings you can feed into generation.
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {tabs.map((t) => (
          <Button
            key={t.id}
            size="sm"
            variant={tab === t.id ? "default" : "outline"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {tab === "suggestions" && (
        <div className="space-y-3">
          {suggestions.isLoading && <p className="text-sm">Loading suggestions…</p>}
          {suggestions.isError && (
            <p className="text-sm text-destructive">Could not load suggestions. Check API / OpenAI.</p>
          )}
          <div className="grid md:grid-cols-2 gap-4">
            {(suggestions.data?.suggestions || []).map((s, i) => (
              <motion.div
                key={`${s.title}-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="rounded-2xl border border-border p-4 bg-background/40 space-y-3"
              >
                <div className="text-xs uppercase tracking-wide text-primary">{s.angle}</div>
                <h3 className="font-display text-lg">{s.title}</h3>
                <p className="text-sm text-muted-foreground">{s.why}</p>
                <p className="text-sm whitespace-pre-wrap line-clamp-4">{s.brief}</p>
                <Button asChild size="sm">
                  <Link to={`/agent?brief=${encodeURIComponent(s.brief)}`}>Generate from this</Link>
                </Button>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {tab === "news" && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Industry: {news.data?.industry || "from company training"} · AI briefings for ideation (live RSS can
            be wired later).
          </p>
          {news.isLoading && <p className="text-sm">Loading industry briefings…</p>}
          <div className="grid gap-4">
            {(news.data?.items || []).map((n, i) => (
              <motion.article
                key={`${n.headline}-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-border p-4 bg-background/40 space-y-2"
              >
                <h3 className="font-display text-xl">{n.headline}</h3>
                <p className="text-sm">{n.summary}</p>
                <p className="text-xs text-muted-foreground">{n.sourceNote}</p>
                <Button asChild size="sm" variant="secondary">
                  <Link
                    to={`/agent?brief=${encodeURIComponent(n.suggestedBrief)}&news=${encodeURIComponent(n.summary)}`}
                  >
                    Use as generation context
                  </Link>
                </Button>
              </motion.article>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
