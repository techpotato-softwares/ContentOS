import { useMemo, useState } from "react"
import {
  useListPostsQuery,
  useSubmitReviewMutation,
  useApprovePostMutation,
  useRejectPostMutation,
  usePublishPostMutation,
  useQuickPublishPostMutation,
  useScorePostMutation,
  useLinkedInStatusQuery,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { PostMedia } from "@/shared/ui/PostMedia"
import { cn } from "@/shared/lib/utils"
import { mediaSrc } from "@/shared/lib/media"
import { linkedInPublishErrorMessage } from "@/shared/lib/linkedinPublishErrors"
import { Link } from "react-router-dom"

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

function CarouselPreview({
  slides,
}: {
  slides: Array<{ headline?: string; body?: string; imageUrl?: string }>
}) {
  const [idx, setIdx] = useState(0)
  if (!slides.length) return null
  const slide = slides[Math.min(idx, slides.length - 1)]
  const src = mediaSrc(slide.imageUrl)
  return (
    <div className="space-y-2">
      {src ? (
        <img src={src} alt="" className="w-full aspect-square object-cover bg-muted" />
      ) : (
        <div className="w-full aspect-square bg-muted flex items-center justify-center p-4 text-center">
          <div>
            <p className="font-display text-lg">{slide.headline}</p>
            <p className="text-xs text-muted-foreground mt-1">{slide.body}</p>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between px-3 text-xs">
        <Button
          size="sm"
          variant="ghost"
          className="h-7"
          disabled={idx <= 0}
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
        >
          Prev
        </Button>
        <span className="text-muted-foreground">
          {idx + 1} / {slides.length}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-7"
          disabled={idx >= slides.length - 1}
          onClick={() => setIdx((i) => Math.min(slides.length - 1, i + 1))}
        >
          Next
        </Button>
      </div>
    </div>
  )
}

export function ReviewPage() {
  const { data: posts = [], isLoading, refetch } = useListPostsQuery()
  const { data: liStatus } = useLinkedInStatusQuery()
  const [submit] = useSubmitReviewMutation()
  const [approve] = useApprovePostMutation()
  const [reject] = useRejectPostMutation()
  const [publish, publishState] = usePublishPostMutation()
  const [quickPublish, quickState] = useQuickPublishPostMutation()
  const [scorePost, scoreState] = useScorePostMutation()
  const [publishAs, setPublishAs] = useState<"member" | "organization" | "auto">("auto")
  const [publishError, setPublishError] = useState<string | null>(null)

  const destinations = useMemo(() => {
    const opts: Array<{ value: "member" | "organization" | "auto"; label: string }> = [
      { value: "auto", label: "Auto (page if connected)" },
    ]
    if (liStatus?.member?.connected) {
      opts.push({
        value: "member",
        label: `Personal (${liStatus.member.username || "profile"})`,
      })
    }
    if (liStatus?.organization?.connected) {
      opts.push({
        value: "organization",
        label: `Company (${liStatus.organization.username || "page"})`,
      })
    }
    return opts
  }, [liStatus])

  const bothConnected =
    Boolean(liStatus?.member?.connected) && Boolean(liStatus?.organization?.connected)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">Review & publish</h1>
        <p className="text-sm text-muted-foreground">
          Score drafts, approve, then publish text / image / carousel to LinkedIn.
        </p>
        {liStatus?.carousel && (
          <p className="text-xs text-muted-foreground mt-2">
            {liStatus.carousel.enabled
              ? "Carousels publish as a LinkedIn PDF document (Documents API)."
              : liStatus.carousel.message}{" "}
            {!liStatus?.member?.connected && !liStatus?.organization?.connected && (
              <>
                <Link to="/connections/linkedin" className="text-primary underline">
                  Connect LinkedIn
                </Link>{" "}
                before publishing.
              </>
            )}
          </p>
        )}
      </div>
      {bothConnected && (
        <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 text-sm">
          <span className="text-muted-foreground">Publish as</span>
          <select
            className="h-11 sm:h-8 w-full sm:w-auto rounded-md border border-border bg-background px-2 text-sm sm:text-xs"
            value={publishAs}
            onChange={(e) =>
              setPublishAs(e.target.value as "member" | "organization" | "auto")
            }
          >
            {destinations.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {publishError && <p className="text-sm text-destructive">{publishError}</p>}
      {isLoading && <p className="text-sm">Loading…</p>}
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {posts.map((p, i) => {
          const fmt = p.format || p.layout?.format || (p.imageUrl ? "image" : "text")
          const slides = p.slides || p.layout?.slides || []
          return (
            <motion.div
              key={p.postId}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-3xl border border-border overflow-hidden bg-card/50 backdrop-blur-sm shadow-sm hover:shadow-elevated transition-shadow"
            >
              {fmt === "carousel" && slides.length > 0 ? (
                <CarouselPreview slides={slides} />
              ) : fmt === "text" ? (
                <div className="px-4 pt-4 space-y-2">
                  {p.imageUrl && (
                    <PostMedia
                      imageUrl={p.imageUrl}
                      filename={`contentos-text-${p.postId}.png`}
                    />
                  )}
                  <div className="rounded-2xl border border-border bg-muted/30 p-4 min-h-35">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
                      Research text{p.imageUrl || p.attachedImage ? " + image" : ""}
                    </p>
                    <p className="text-sm whitespace-pre-wrap line-clamp-12">{p.caption}</p>
                    {(p.hashtags || p.layout?.hashtags)?.length ? (
                      <p className="text-xs text-primary mt-3">
                        {(p.hashtags || p.layout?.hashtags || []).join(" ")}
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : !p.imageUrl ? (
                <div className="px-4 pt-4">
                  <div className="rounded-2xl border border-border bg-muted/30 p-4 min-h-35">
                    <p className="text-sm whitespace-pre-wrap line-clamp-8">{p.caption}</p>
                  </div>
                </div>
              ) : (
                <PostMedia
                  imageUrl={p.imageUrl}
                  filename={`contentos-post-${p.postId}.png`}
                />
              )}
              <div className="p-4 pt-0 space-y-3">
                <div className="flex justify-between items-start gap-2 text-xs">
                  <span className="text-primary uppercase">
                    {p.angle}
                    {fmt !== "image" ? ` · ${fmt}` : ""}
                  </span>
                  <StatusChips status={p.status} />
                </div>
                {(p.headline || p.layout?.headline) && fmt !== "text" && (
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
                {fmt !== "text" && (
                  <p className="text-sm line-clamp-4 whitespace-pre-wrap">{p.caption}</p>
                )}
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
                  {fmt === "carousel" && !liStatus?.carousel?.enabled && (
                    <p className="text-xs text-destructive">
                      Carousel publish is disabled — convert to image/text or enable Documents API.
                    </p>
                  )}
                  {p.status !== "published" && p.status !== "rejected" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={
                        quickState.isLoading ||
                        publishState.isLoading ||
                        (fmt === "carousel" && liStatus?.carousel?.enabled === false)
                      }
                      onClick={async () => {
                        setPublishError(null)
                        try {
                          await quickPublish(
                            publishAs === "auto"
                              ? p.postId
                              : { id: p.postId, publishAs },
                          ).unwrap()
                          void refetch()
                        } catch (e: unknown) {
                          setPublishError(linkedInPublishErrorMessage(e))
                        }
                      }}
                    >
                      Post to LinkedIn
                    </Button>
                  )}
                  {p.status === "approved" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={
                        publishState.isLoading ||
                        (fmt === "carousel" && liStatus?.carousel?.enabled === false)
                      }
                      onClick={async () => {
                        setPublishError(null)
                        try {
                          await publish(
                            publishAs === "auto"
                              ? p.postId
                              : { id: p.postId, publishAs },
                          ).unwrap()
                          void refetch()
                        } catch (e: unknown) {
                          setPublishError(linkedInPublishErrorMessage(e))
                        }
                      }}
                    >
                      {p.scheduledAt ? "Publish now" : "Publish (approved)"}
                    </Button>
                  )}
                  {p.status === "published" && (
                    <span className="text-xs text-primary">Published {p.linkedinPostId}</span>
                  )}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
