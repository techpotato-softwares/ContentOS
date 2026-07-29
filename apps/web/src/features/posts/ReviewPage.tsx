import {
  useListPostsQuery,
  useSubmitReviewMutation,
  useApprovePostMutation,
  useRejectPostMutation,
  usePublishPostMutation,
  useScorePostMutation,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { PostMedia } from "@/shared/ui/PostMedia"
import { cn } from "@/shared/lib/utils"

const PIPELINE = ["draft", "pending_review", "approved", "published"] as const

function StatusChips({ status }: { status: string }) {
  const idx = PIPELINE.indexOf(status as (typeof PIPELINE)[number])
  const labels: Record<string, string> = {
    draft: "Draft",
    pending_review: "In review",
    approved: "Approved",
    published: "Published",
    rejected: "Rejected",
  }
  if (status === "rejected") {
    return (
      <span className="text-[10px] uppercase tracking-wide rounded-full px-2 py-0.5 bg-destructive/15 text-destructive">
        Rejected
      </span>
    )
  }
  return (
    <div className="flex flex-wrap gap-1">
      {PIPELINE.map((s, i) => (
        <span
          key={s}
          className={cn(
            "text-[10px] uppercase tracking-wide rounded-full px-2 py-0.5 border",
            i <= idx
              ? "bg-primary/15 text-primary border-primary/30"
              : "border-border text-muted-foreground",
          )}
        >
          {labels[s]}
        </span>
      ))}
    </div>
  )
}

export function ReviewPage() {
  const { data: posts = [], isLoading, refetch } = useListPostsQuery()
  const [submit] = useSubmitReviewMutation()
  const [approve] = useApprovePostMutation()
  const [reject] = useRejectPostMutation()
  const [publish] = usePublishPostMutation()
  const [scorePost, scoreState] = useScorePostMutation()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl">Review & publish</h1>
        <p className="text-sm text-muted-foreground">
          Score drafts, approve, then publish now — or wait for scheduled A/B slots.
        </p>
      </div>
      {isLoading && <p className="text-sm">Loading…</p>}
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {posts.map((p, i) => (
          <motion.div
            key={p.postId}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="rounded-3xl border border-border overflow-hidden bg-card/50 backdrop-blur-sm shadow-sm hover:shadow-elevated transition-shadow"
          >
            <PostMedia
              imageUrl={p.imageUrl}
              filename={`contentos-post-${p.postId}.png`}
            />
            <div className="p-4 pt-0 space-y-3">
              <div className="flex justify-between items-start gap-2 text-xs">
                <span className="text-primary uppercase">{p.angle}</span>
                <StatusChips status={p.status} />
              </div>
              {(p.headline || p.layout?.headline) && (
                <h3 className="font-display text-lg leading-snug">
                  {p.headline || p.layout?.headline}
                </h3>
              )}
              {(p.abLabel || p.scheduledAt) && (
                <div className="text-[11px] text-muted-foreground flex flex-wrap gap-2">
                  {p.abLabel && <span className="text-primary">Variant {p.abLabel}</span>}
                  {p.scheduledAt && (
                    <span>Scheduled {new Date(p.scheduledAt).toLocaleString()}</span>
                  )}
                </div>
              )}
              <p className="text-sm line-clamp-4 whitespace-pre-wrap">{p.caption}</p>
              {p.score && (
                <div className="rounded-xl border border-border bg-muted/40 px-3 py-2 text-xs space-y-1">
                  <div className="flex justify-between">
                    <span>AI score</span>
                    <span className="font-display text-base">{p.score.overall}</span>
                  </div>
                  <p className="text-muted-foreground line-clamp-2">{p.score.summary}</p>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={scoreState.isLoading}
                  onClick={async () => {
                    await scorePost(p.postId)
                    void refetch()
                  }}
                >
                  {p.score ? "Re-score" : "Score"}
                </Button>
                {p.status === "draft" && (
                  <Button size="sm" onClick={() => void submit(p.postId)}>
                    Submit review
                  </Button>
                )}
                {(p.status === "pending_review" || p.status === "draft") && (
                  <>
                    <Button size="sm" onClick={() => void approve(p.postId)}>
                      Approve
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => void reject(p.postId)}>
                      Reject
                    </Button>
                  </>
                )}
                {p.status === "approved" && (
                  <Button size="sm" variant="secondary" onClick={() => void publish(p.postId)}>
                    {p.scheduledAt ? "Publish now" : "Publish to LinkedIn"}
                  </Button>
                )}
                {p.status === "published" && (
                  <span className="text-xs text-primary">Published {p.linkedinPostId}</span>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
