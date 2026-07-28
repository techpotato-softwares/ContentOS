import {
  useListPostsQuery,
  useSubmitReviewMutation,
  useApprovePostMutation,
  useRejectPostMutation,
  usePublishPostMutation,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { PostMedia } from "@/shared/ui/PostMedia"

export function ReviewPage() {
  const { data: posts = [], isLoading } = useListPostsQuery()
  const [submit] = useSubmitReviewMutation()
  const [approve] = useApprovePostMutation()
  const [reject] = useRejectPostMutation()
  const [publish] = usePublishPostMutation()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl">Review & publish</h1>
        <p className="text-sm text-muted-foreground">
          Manual gate required — only approved posts can be published to LinkedIn.
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
              <div className="flex justify-between text-xs">
                <span className="text-primary uppercase">{p.angle}</span>
                <span className="text-muted-foreground">{p.status}</span>
              </div>
              <p className="text-sm line-clamp-4 whitespace-pre-wrap">{p.caption}</p>
              <div className="flex flex-wrap gap-2">
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
                    Publish to LinkedIn
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
