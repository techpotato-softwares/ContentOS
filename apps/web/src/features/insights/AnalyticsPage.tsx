import { Link } from "react-router-dom"
import { useGetAnalyticsInsightsQuery } from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"

export function AnalyticsPage() {
  const { data, isLoading, isError } = useGetAnalyticsInsightsQuery()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl">Analytics</h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          LinkedIn performance overview and AI guidance on what and when to publish for better reach.
        </p>
      </div>

      {isLoading && <p className="text-sm">Loading analytics…</p>}
      {isError && <p className="text-sm text-destructive">Could not load analytics insights.</p>}

      {data && (
        <>
          <div className="rounded-2xl border border-dashed border-border p-4 bg-muted/30 text-sm">
            Placeholder LinkedIn analytics — connect the LinkedIn Analytics API for live numbers. Advice below
            uses sample metrics plus your company context.
          </div>
          <div className="grid sm:grid-cols-4 gap-3">
            {[
              ["Followers", data.metrics?.followers],
              ["Impressions (28d)", data.metrics?.impressions28d],
              ["Engagement %", data.metrics?.engagementRate],
              ["Avg reach", data.metrics?.avgReach],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-2xl border border-border p-4">
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="font-display text-2xl mt-1">{value ?? "—"}</div>
              </div>
            ))}
          </div>
          <p className="text-sm">{data.summary}</p>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-2xl border border-border p-4 space-y-2">
              <h3 className="font-display text-lg">When to publish</h3>
              <ul className="text-sm space-y-1 list-disc pl-4">
                {(data.bestTimes || []).map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-2xl border border-border p-4 space-y-2">
              <h3 className="font-display text-lg">What to publish</h3>
              <ul className="text-sm space-y-1 list-disc pl-4">
                {(data.suggestedTopics || []).map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="rounded-2xl border border-border p-4 space-y-2">
            <h3 className="font-display text-lg">AI recommendations</h3>
            <ul className="text-sm space-y-2 list-disc pl-4">
              {(data.recommendations || []).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <Button asChild size="sm" className="mt-2">
              <Link to="/agent">Open agent to generate</Link>
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
