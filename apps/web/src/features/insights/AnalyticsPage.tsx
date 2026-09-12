import { Link } from "react-router-dom"
import {
  useGetAnalyticsInsightsQuery,
  useGetWeeklySnapshotQuery,
  useSendWeeklySnapshotMutation,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"

export function AnalyticsPage() {
  const { data, isLoading, isError } = useGetAnalyticsInsightsQuery()
  const { data: weekly, isLoading: weeklyLoading, refetch } = useGetWeeklySnapshotQuery()
  const [sendWeekly, sendState] = useSendWeeklySnapshotMutation()
  const stats = weekly?.stats

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">Analytics</h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Team performance snapshot and AI guidance on what and when to publish.
        </p>
      </div>

      <section className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="font-display text-xl">Weekly team snapshot</h2>
          <div className="grid grid-cols-2 sm:flex gap-2">
            <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={() => void refetch()}>
              Refresh
            </Button>
            <Button
              size="sm"
              variant="secondary"
              className="w-full sm:w-auto"
              disabled={sendState.isLoading}
              onClick={async () => {
                await sendWeekly()
                void refetch()
              }}
            >
              {sendState.isLoading ? "Sending…" : "Email via SES"}
            </Button>
          </div>
        </div>
        {weeklyLoading && <p className="text-sm">Loading snapshot…</p>}
        {stats && (
          <>
            <p className="text-xs text-muted-foreground">
              {stats.periodStart} → {stats.periodEnd}
              {sendState.isSuccess && " · Email queued / sent (see SES_ENABLED)"}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                ["Generated", stats.generated],
                ["Batches", stats.batches],
                ["Draft", stats.draft],
                ["In review", stats.pendingReview],
                ["Approved", stats.approved],
                ["Published", stats.published],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="font-display text-2xl mt-1">{value}</div>
                </div>
              ))}
            </div>
            {stats.topPost && (
              <div className="rounded-2xl border border-border p-4 text-sm">
                <div className="text-xs text-muted-foreground mb-1">Highlight</div>
                <div className="font-medium">
                  #{stats.topPost.postId} · {stats.topPost.angle}
                </div>
                <p className="text-muted-foreground mt-1">
                  {stats.topPost.headline || stats.topPost.captionPreview}
                </p>
              </div>
            )}
          </>
        )}
      </section>

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
