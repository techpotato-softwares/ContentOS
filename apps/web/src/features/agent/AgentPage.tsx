import { useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import {
  MessageSquarePlus,
  History,
  Loader2,
  Clock,
  Link2,
  FileUp,
  Sparkles,
  Gauge,
  Square,
  X,
  RotateCcw,
} from "lucide-react"
import {
  useChatMutation,
  useGenerateMutation,
  useListSessionsQuery,
  useLazyGetSessionMessagesQuery,
  useGetImageModelsQuery,
  useScorePostMutation,
  useScoreBatchMutation,
  useRepurposeMutation,
  useAbScheduleMutation,
  useQuickPublishPostMutation,
  useLinkedInStatusQuery,
  type ContentPost,
  type AbScheduleSuggestion,
  type PostScore,
  type GenerationBatchRow,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/input"
import { PostMedia } from "@/shared/ui/PostMedia"
import { cn } from "@/shared/lib/utils"

type Msg = { role: "user" | "assistant"; content: string }

type PendingDraft =
  | { kind: "brief"; text: string }
  | { kind: "url"; url: string }
  | { kind: "pdf"; file: File; name: string }

const GEN_STAGES = [
  { afterSec: 0, label: "Planning on-brand variants" },
  { afterSec: 8, label: "Fact-checking against context" },
  { afterSec: 18, label: "Generating right-side visuals" },
  { afterSec: 45, label: "Composing crisp brand overlay" },
  { afterSec: 75, label: "Uploading creatives" },
]

function formatElapsed(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
}

function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false
  const e = err as { name?: string; message?: string; status?: string; error?: string }
  if (e.name === "AbortError") return true
  const blob = `${e.message || ""} ${e.error || ""} ${e.status || ""}`.toLowerCase()
  return blob.includes("abort")
}

function ScoreBadge({ score }: { score: PostScore }) {
  const color =
    score.overall >= 80
      ? "border-emerald-500/35 bg-emerald-500/10"
      : score.overall >= 65
        ? "border-amber-500/35 bg-amber-500/10"
        : "border-destructive/35 bg-destructive/10"
  return (
    <div className={cn("rounded-xl border p-2.5 space-y-1.5 text-[11px]", color)}>
      <div className="flex items-center justify-between gap-2">
        <span className="uppercase tracking-wide text-muted-foreground">Score</span>
        <span className="font-display text-lg tabular-nums leading-none">{score.overall}</span>
      </div>
      <div className="grid grid-cols-4 gap-1">
        {[
          ["Cl", score.clarity],
          ["Hk", score.hook],
          ["Br", score.brandFit],
          ["CTA", score.cta],
        ].map(([label, val]) => (
          <div key={String(label)} className="rounded-md bg-background/60 px-1 py-0.5 text-center">
            <div className="text-[9px] text-muted-foreground">{label}</div>
            <div className="font-medium tabular-nums">{val}</div>
          </div>
        ))}
      </div>
      <p className="text-muted-foreground line-clamp-2 leading-snug">{score.summary}</p>
    </div>
  )
}

function PostCard({
  p,
  scoring,
  posting,
  onScore,
  onPostLinkedIn,
}: {
  p: ContentPost
  scoring: boolean
  posting?: boolean
  onScore: (id: number) => void
  onPostLinkedIn?: (id: number) => void
}) {
  const fmt = p.format || p.layout?.format || (p.imageUrl ? "image" : "text")
  const slides = p.slides || p.layout?.slides || []
  const tags = p.hashtags || p.layout?.hashtags || []
  const canPost = p.status !== "published" && p.status !== "rejected"
  return (
    <motion.article
      key={p.postId}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border overflow-hidden bg-card/40"
    >
      {fmt === "carousel" && slides[0]?.imageUrl ? (
        <PostMedia
          compact
          imageUrl={slides[0].imageUrl}
          filename={`contentos-carousel-${p.postId}.png`}
        />
      ) : fmt === "text" ? (
        <div className="px-3 pt-3 space-y-2">
          {p.imageUrl && (
            <PostMedia
              compact
              imageUrl={p.imageUrl}
              filename={`contentos-text-${p.postId}.png`}
            />
          )}
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-[9px] uppercase tracking-wide text-muted-foreground mb-1">
              Research text{p.imageUrl || p.attachedImage ? " + image" : ""}
            </p>
            <p className="text-xs whitespace-pre-wrap line-clamp-10">{p.caption}</p>
            {tags.length > 0 && (
              <p className="text-[10px] text-primary mt-2">{tags.join(" ")}</p>
            )}
          </div>
        </div>
      ) : !p.imageUrl ? (
        <div className="px-3 pt-3">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-xs whitespace-pre-wrap line-clamp-6">{p.caption}</p>
          </div>
        </div>
      ) : (
        <PostMedia compact imageUrl={p.imageUrl} filename={`contentos-post-${p.postId}.png`} />
      )}
      <div className="px-3 pb-3 space-y-2">
        <div className="flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide">
          <span className="text-primary">
            {p.angle}
            {fmt !== "image" ? ` · ${fmt}` : ""}
          </span>
          <span className="text-muted-foreground normal-case">
            {p.abLabel ? `Var ${p.abLabel} · ` : ""}#{p.postId}
          </span>
        </div>
        {(p.headline || p.layout?.headline) && fmt !== "text" && (
          <h3 className="font-display text-base leading-snug">
            {p.headline || p.layout?.headline}
          </h3>
        )}
        {fmt !== "text" && (
          <p className="text-xs text-muted-foreground line-clamp-3 whitespace-pre-wrap">
            {p.caption}
          </p>
        )}
        {fmt === "carousel" && slides.length > 0 && (
          <p className="text-[10px] text-muted-foreground">{slides.length} slides ready</p>
        )}
        {p.score && <ScoreBadge score={p.score} />}
        {p.status === "published" && (
          <p className="text-[10px] text-primary">Posted {p.linkedinPostId}</p>
        )}
        <div className="flex flex-wrap gap-1.5">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-[11px]"
            disabled={scoring}
            onClick={() => onScore(p.postId)}
          >
            {p.score ? "Re-score" : "Score"}
          </Button>
          {canPost && onPostLinkedIn && (
            <Button
              size="sm"
              variant="secondary"
              className="h-7 text-[11px]"
              disabled={posting}
              onClick={() => onPostLinkedIn(p.postId)}
            >
              Post to LinkedIn
            </Button>
          )}
        </div>
      </div>
    </motion.article>
  )
}

export function AgentPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Describe a LinkedIn post, or paste a URL / PDF to repurpose. I’ll generate 3 on-brand variants with sharp template text.",
    },
  ])
  const [input, setInput] = useState("")
  const [sessionId, setSessionId] = useState<number | undefined>()
  const [chat, chatState] = useChatMutation()
  const [generate, genState] = useGenerateMutation()
  const [scorePost, scoreState] = useScorePostMutation()
  const [scoreBatch, scoreBatchState] = useScoreBatchMutation()
  const [repurpose, repurposeState] = useRepurposeMutation()
  const [abSchedule, abState] = useAbScheduleMutation()
  const { data: sessions = [], refetch: refetchSessions } = useListSessionsQuery()
  const { data: modelsPayload } = useGetImageModelsQuery()
  const [loadMessages] = useLazyGetSessionMessagesQuery()
  const [posts, setPosts] = useState<ContentPost[]>([])
  const [batches, setBatches] = useState<GenerationBatchRow[]>([])
  const [batchId, setBatchId] = useState<number | undefined>()
  const [suggestions, setSuggestions] = useState<AbScheduleSuggestion[]>([])
  const [strategy, setStrategy] = useState<string | null>(null)
  const [preset, setPreset] = useState("linkedin_landscape")
  const [renderMode, setRenderMode] = useState<"template" | "native_text">("template")
  const [imageModel, setImageModel] = useState("gpt-image-1")
  const [aiProvider, setAiProvider] = useState("openai")
  const [elapsed, setElapsed] = useState(0)
  const [genError, setGenError] = useState<string | null>(null)
  const [repurposeUrl, setRepurposeUrl] = useState("")
  const [pendingPdf, setPendingPdf] = useState<{ file: File; name: string } | null>(null)
  const [stagedPdf, setStagedPdf] = useState<{
    file: File
    name: string
    b64: string
    extractBrief?: string
    title?: string
  } | null>(null)
  const [stagedUrl, setStagedUrl] = useState<{
    url: string
    extractBrief?: string
    title?: string
  } | null>(null)
  const [postFormat, setPostFormat] = useState<"text" | "image" | "carousel">("image")
  const [attachImage, setAttachImage] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [draftNotice, setDraftNotice] = useState<string | null>(null)
  const [mobilePane, setMobilePane] = useState<"chats" | "brief" | "artifacts">("brief")
  const [quickPublish, quickPublishState] = useQuickPublishPostMutation()
  const { data: liStatus } = useLinkedInStatusQuery()
  const linkedInReady = Boolean(
    liStatus?.member?.connected || liStatus?.organization?.connected || liStatus?.connected,
  )
  const fileRef = useRef<HTMLInputElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<{ abort: () => void } | null>(null)
  const draftRef = useRef<PendingDraft | null>(null)
  const optimisticUserRef = useRef<string | null>(null)
  const busy = genState.isLoading || (repurposeState.isLoading && !extracting)

  useEffect(() => {
    if (modelsPayload?.defaultPreset) setPreset(modelsPayload.defaultPreset)
    const firstAvail = modelsPayload?.models?.find((m) => m.available)
    if (firstAvail) setImageModel(firstAvail.id)
    if (modelsPayload?.defaultTextProvider) {
      setAiProvider(modelsPayload.defaultTextProvider)
    } else {
      const textAvail = modelsPayload?.textProviders?.find((p) => p.available)
      if (textAvail) setAiProvider(textAvail.id)
    }
  }, [modelsPayload])

  useEffect(() => {
    const prefill = searchParams.get("brief")
    const news = searchParams.get("news")
    if (prefill) {
      setInput(prefill + (news ? `\n\nUse this industry context:\n${news}` : ""))
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!busy) return
    setElapsed(0)
    const started = Date.now()
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000))
    }, 250)
    return () => window.clearInterval(id)
  }, [busy])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, busy])

  const stageLabel = useMemo(() => {
    let label = GEN_STAGES[0].label
    for (const s of GEN_STAGES) {
      if (elapsed >= s.afterSec) label = s.label
    }
    return label
  }, [elapsed])

  const stageIndex = useMemo(() => {
    let idx = 0
    GEN_STAGES.forEach((s, i) => {
      if (elapsed >= s.afterSec) idx = i
    })
    return idx
  }, [elapsed])

  const applyArtifacts = (res: {
    posts?: ContentPost[]
    batches?: GenerationBatchRow[]
    batchId?: number | null
  }) => {
    if (res.batches?.length) {
      setBatches(res.batches)
      setPosts(res.batches.flatMap((b) => b.posts || []))
      setBatchId(res.batches[res.batches.length - 1]?.batchId)
    } else {
      setBatches([])
      setPosts(res.posts || [])
      setBatchId(res.batchId ?? undefined)
    }
  }

  const mergeNewBatch = (newPosts: ContentPost[], newBatchId?: number, brief?: string) => {
    if (!newPosts.length) return
    const bid = newBatchId ?? newPosts[0]?.batchId
    const row: GenerationBatchRow = {
      batchId: bid || Date.now(),
      brief,
      createdAt: new Date().toISOString(),
      status: "completed",
      posts: newPosts,
    }
    setBatches((prev) => [...prev.filter((b) => b.batchId !== row.batchId), row])
    setPosts((prev) => {
      const ids = new Set(newPosts.map((p) => p.postId))
      return [...prev.filter((p) => !ids.has(p.postId)), ...newPosts]
    })
    if (bid) setBatchId(bid)
  }

  const restoreDraft = (draft: PendingDraft | null) => {
    if (!draft) return
    if (draft.kind === "brief") {
      setInput(draft.text)
      setDraftNotice("Draft restored — edit and generate again when ready.")
    } else if (draft.kind === "url") {
      setRepurposeUrl(draft.url)
      setDraftNotice("URL draft restored — stage it again or click Go when ready.")
    } else {
      setPendingPdf({ file: draft.file, name: draft.name })
      setDraftNotice(`PDF “${draft.name}” kept — click Retry PDF when ready.`)
    }
  }

  const dropOptimisticUser = () => {
    const note = optimisticUserRef.current
    if (!note) return
    setMessages((m) => {
      const last = m[m.length - 1]
      if (last?.role === "user" && last.content === note) return m.slice(0, -1)
      return m
    })
    optimisticUserRef.current = null
  }

  const cancelGenerate = () => {
    abortRef.current?.abort()
  }

  const openSession = async (id: number) => {
    if (busy) cancelGenerate()
    const res = await loadMessages(id).unwrap()
    setSessionId(res.sessionId)
    const mapped: Msg[] = res.messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }))
    setMessages(
      mapped.length
        ? mapped
        : [{ role: "assistant", content: "Continue this chat or generate variants." }],
    )
    applyArtifacts(res)
    setSuggestions([])
    setStrategy(null)
    setDraftNotice(null)
    setPendingPdf(null)
    setStagedPdf(null)
    setStagedUrl(null)
  }

  const newChat = () => {
    if (busy) cancelGenerate()
    setSessionId(undefined)
    setPosts([])
    setBatches([])
    setBatchId(undefined)
    setSuggestions([])
    setStrategy(null)
    setPendingPdf(null)
    setStagedPdf(null)
    setStagedUrl(null)
    setDraftNotice(null)
    setMessages([
      {
        role: "assistant",
        content: "New chat — describe the LinkedIn post you want.",
      },
    ])
  }

  const send = async () => {
    if (busy) return
    const text = input.trim()
    // Claude-style: staged PDF/URL + optional context → generate on Send
    if (stagedPdf || stagedUrl) {
      await runStagedGenerate(text)
      return
    }
    if (!text) return
    setInput("")
    setMessages((m) => [...m, { role: "user", content: text }])
    try {
      const res = await chat({ message: text, sessionId, aiProvider }).unwrap()
      setSessionId(res.sessionId)
      setMessages((m) => [...m, { role: "assistant", content: res.reply }])
      void refetchSessions()
    } catch {
      setInput(text)
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Chat failed — check the API and try again." },
      ])
    }
  }

  const runStagedGenerate = async (userContext: string) => {
    setGenError(null)
    setDraftNotice(null)
    const contextNote = userContext.trim()
    if (stagedPdf) {
      const note = contextNote
        ? `Repurpose PDF: ${stagedPdf.name}\n\n${contextNote}`
        : `Repurpose PDF: ${stagedPdf.name}`
      optimisticUserRef.current = note
      setMessages((m) => [...m, { role: "user", content: note }])
      setInput("")
      const req = repurpose({
        pdfBase64: stagedPdf.b64,
        filename: stagedPdf.name,
        generate: true,
        userContext: contextNote || undefined,
        format: postFormat,
        attachImage: postFormat === "text" ? attachImage : undefined,
        sessionId,
        preset,
        renderMode,
        imageModel,
        aiProvider,
      })
      abortRef.current = req
      try {
        const res = await req.unwrap()
        abortRef.current = null
        optimisticUserRef.current = null
        setStagedPdf(null)
        if (res.sessionId) setSessionId(res.sessionId)
        mergeNewBatch(res.posts || [], res.batchId, note)
        setSuggestions([])
        setStrategy(null)
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `Generated ${res.posts?.length || 0} ${postFormat} ${
              (res.posts?.length || 0) === 1 ? "post" : "variants"
            } from “${res.extracted?.title || stagedPdf.name}”.`,
          },
        ])
        void refetchSessions()
      } catch (err) {
        abortRef.current = null
        dropOptimisticUser()
        setGenError("PDF generate failed — check the file and try again.")
      }
      return
    }
    if (stagedUrl) {
      const note = contextNote
        ? `Repurpose: ${stagedUrl.url}\n\n${contextNote}`
        : `Repurpose: ${stagedUrl.url}`
      optimisticUserRef.current = note
      setMessages((m) => [...m, { role: "user", content: note }])
      setInput("")
      const req = repurpose({
        url: stagedUrl.url,
        generate: true,
        userContext: contextNote || undefined,
        format: postFormat,
        attachImage: postFormat === "text" ? attachImage : undefined,
        sessionId,
        preset,
        renderMode,
        imageModel,
        aiProvider,
      })
      abortRef.current = req
      try {
        const res = await req.unwrap()
        abortRef.current = null
        optimisticUserRef.current = null
        setStagedUrl(null)
        if (res.sessionId) setSessionId(res.sessionId)
        mergeNewBatch(res.posts || [], res.batchId, note)
        setSuggestions([])
        setStrategy(null)
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `Generated ${res.posts?.length || 0} ${postFormat} ${
              (res.posts?.length || 0) === 1 ? "post" : "variants"
            } from “${res.extracted?.title || "URL"}”.`,
          },
        ])
        void refetchSessions()
      } catch (err) {
        abortRef.current = null
        dropOptimisticUser()
        setGenError("URL generate failed — link may be blocked or empty.")
      }
    }
  }

  const PLACEHOLDER_SEND = (() => {
    if (stagedPdf) return "Add context for this PDF, then Send to generate…"
    if (stagedUrl) return "Add context for this URL, then Send to generate…"
    return "What should this LinkedIn post say?"
  })()

  const onGenerate = async () => {
    if (stagedPdf || stagedUrl) {
      await runStagedGenerate(input.trim())
      return
    }
    const brief =
      input.trim() ||
      [...messages].reverse().find((m) => m.role === "user")?.content ||
      "Create an informative branded LinkedIn image post for our company"
    const draft: PendingDraft = { kind: "brief", text: input.trim() || brief }
    draftRef.current = draft
    setGenError(null)
    setDraftNotice(null)
    if (input.trim()) setInput("")

    const req = generate({
      brief,
      sessionId,
      preset,
      format: postFormat,
      attachImage: postFormat === "text" ? attachImage : undefined,
      renderMode,
      imageModel,
      aiProvider,
    })
    abortRef.current = req
    try {
      const res = await req.unwrap()
      abortRef.current = null
      draftRef.current = null
      if (res.sessionId) setSessionId(res.sessionId)
      mergeNewBatch(res.posts, res.batchId, brief)
      setSuggestions([])
      setStrategy(null)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Ready — ${res.posts.length} ${postFormat} ${
            res.posts.length === 1 ? "post" : "variants"
          } (batch #${res.batchId}). Score the batch or apply an A/B schedule.`,
        },
      ])
      void refetchSessions()
    } catch (err) {
      abortRef.current = null
      if (isAbortError(err)) {
        dropOptimisticUser()
        restoreDraft(draftRef.current)
        setGenError(null)
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "Stopped — your draft was preserved." },
        ])
      } else {
        restoreDraft(draftRef.current)
        setGenError(`Generation failed after ${formatElapsed(elapsed)}. Check OpenAI quota, then retry.`)
      }
    }
  }

  const onRepurposeUrl = async () => {
    if (!repurposeUrl.trim()) return
    const url = repurposeUrl.trim()
    setGenError(null)
    setExtracting(true)
    try {
      const res = await repurpose({
        url,
        generate: false,
        sessionId,
      }).unwrap()
      setStagedUrl({
        url,
        extractBrief: res.extracted?.brief,
        title: res.extracted?.title,
      })
      setStagedPdf(null)
      setRepurposeUrl("")
      setDraftNotice(
        `URL “${res.extracted?.title || url}” attached — add context below, then Send.`,
      )
    } catch {
      setGenError("Could not extract that URL — check the link.")
    } finally {
      setExtracting(false)
    }
  }

  const runPdf = async (file: File) => {
    const draft: PendingDraft = { kind: "pdf", file, name: file.name }
    draftRef.current = draft
    setPendingPdf({ file, name: file.name })
    setGenError(null)
    setDraftNotice(null)

    const reader = new FileReader()
    const b64 = await new Promise<string>((resolve, reject) => {
      reader.onload = () => {
        const result = String(reader.result || "")
        resolve(result.includes(",") ? result.split(",", 2)[1] : result)
      }
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(file)
    })

    const note = `Repurpose PDF: ${file.name}`
    optimisticUserRef.current = note
    setMessages((m) => [...m, { role: "user", content: note }])

    const req = repurpose({
      pdfBase64: b64,
      filename: file.name,
      generate: true,
      format: postFormat,
      attachImage: postFormat === "text" ? attachImage : undefined,
      sessionId,
      preset,
      renderMode,
      imageModel,
      aiProvider,
    })
    abortRef.current = req
    try {
      const res = await req.unwrap()
      abortRef.current = null
      draftRef.current = null
      optimisticUserRef.current = null
      setPendingPdf(null)
      if (res.sessionId) setSessionId(res.sessionId)
      mergeNewBatch(res.posts || [], res.batchId, note)
      setSuggestions([])
      setStrategy(null)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Repurposed “${res.extracted?.title || file.name}” into ${res.posts?.length || 0} variants.`,
        },
      ])
      void refetchSessions()
    } catch (err) {
      abortRef.current = null
      if (isAbortError(err)) {
        dropOptimisticUser()
        restoreDraft(draftRef.current)
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "Stopped — PDF draft was kept for retry." },
        ])
      } else {
        dropOptimisticUser()
        restoreDraft(draftRef.current)
        setGenError("PDF repurpose failed — use a text PDF under 12MB.")
      }
    }
  }

  const stagePdf = async (file: File) => {
    setGenError(null)
    setExtracting(true)
    try {
      const reader = new FileReader()
      const b64 = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const result = String(reader.result || "")
          resolve(result.includes(",") ? result.split(",", 2)[1] : result)
        }
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(file)
      })
      const res = await repurpose({
        pdfBase64: b64,
        filename: file.name,
        generate: false,
        sessionId,
      }).unwrap()
      setStagedPdf({
        file,
        name: file.name,
        b64,
        extractBrief: res.extracted?.brief,
        title: res.extracted?.title,
      })
      setStagedUrl(null)
      setPendingPdf(null)
      setDraftNotice(
        `PDF “${res.extracted?.title || file.name}” attached — add context below, then Send.`,
      )
    } catch {
      setPendingPdf({ file, name: file.name })
      setGenError("PDF extract failed — use a text PDF under 12MB, or Retry.")
    } finally {
      setExtracting(false)
    }
  }

  const onRepurposePdf = (file: File) => {
    void stagePdf(file)
  }

  const onScore = async (postId: number) => {
    try {
      const updated = await scorePost(postId).unwrap()
      setPosts((prev) => prev.map((p) => (p.postId === postId ? { ...p, ...updated } : p)))
      setBatches((prev) =>
        prev.map((b) => ({
          ...b,
          posts: b.posts.map((p) => (p.postId === postId ? { ...p, ...updated } : p)),
        })),
      )
    } catch {
      /* ignore */
    }
  }

  const onPostLinkedIn = async (postId: number) => {
    if (!linkedInReady) {
      setGenError("Connect LinkedIn first (Connections → LinkedIn), then post.")
      return
    }
    setGenError(null)
    try {
      const updated = await quickPublish(postId).unwrap()
      setPosts((prev) => prev.map((p) => (p.postId === postId ? { ...p, ...updated } : p)))
      setBatches((prev) =>
        prev.map((b) => ({
          ...b,
          posts: b.posts.map((p) => (p.postId === postId ? { ...p, ...updated } : p)),
        })),
      )
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Posted to LinkedIn (#${postId}${updated.linkedinPostId ? ` · ${updated.linkedinPostId}` : ""}).`,
        },
      ])
    } catch (e: unknown) {
      const msg =
        (e as { data?: { message?: string; error?: string } })?.data?.message ||
        (e as { data?: { error?: string } })?.data?.error ||
        "LinkedIn post failed — check connection and try again."
      setGenError(String(msg))
    }
  }

  const onScoreAll = async () => {
    if (!batchId) return
    try {
      const res = await scoreBatch(batchId).unwrap()
      if (res.posts?.length) {
        const byId = new Map(res.posts.map((p) => [p.postId, p]))
        setPosts((prev) => prev.map((p) => byId.get(p.postId) || p))
        setBatches((prev) =>
          prev.map((b) =>
            b.batchId === batchId
              ? { ...b, posts: b.posts.map((p) => byId.get(p.postId) || p) }
              : b,
          ),
        )
      }
    } catch {
      setGenError("Batch scoring failed.")
    }
  }

  const onSuggestSchedule = async (apply = false) => {
    if (!batchId) return
    try {
      const res = await abSchedule({ batchId, apply }).unwrap()
      setSuggestions(res.suggestions || [])
      setStrategy(res.strategy || null)
      if (apply && res.posts?.length) {
        const byId = new Map(res.posts.map((p) => [p.postId, p]))
        setPosts((prev) => prev.map((p) => byId.get(p.postId) || p))
        setBatches((prev) =>
          prev.map((b) =>
            b.batchId === batchId
              ? { ...b, posts: b.posts.map((p) => byId.get(p.postId) || p) }
              : b,
          ),
        )
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `A/B schedule applied. Approve in Review — auto-publish runs when due.`,
          },
        ])
      }
    } catch {
      setGenError("Could not build A/B schedule.")
    }
  }

  const displayBatches =
    batches.length > 0
      ? [...batches].reverse()
      : posts.length
        ? [
            {
              batchId: batchId || 0,
              posts,
              createdAt: null,
              brief: "Variants",
            } as GenerationBatchRow,
          ]
        : []

  const selectClass =
    "h-11 sm:h-8 w-full sm:w-auto rounded-lg border border-border bg-background/70 px-2 text-xs min-w-0"

  return (
    <div className="flex flex-col h-full min-h-0 gap-3 overflow-hidden">
      <header className="shrink-0 flex flex-col sm:flex-row sm:flex-wrap sm:items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl md:text-3xl leading-tight">Agent</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Brief · URL · PDF → 3 variants → score → schedule
          </p>
        </div>
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 w-full sm:w-auto">
          <select
            className={selectClass}
            value={aiProvider}
            onChange={(e) => setAiProvider(e.target.value)}
            disabled={busy}
            title="Text / planning model (images stay on OpenAI)"
          >
            {(
              modelsPayload?.textProviders || [
                { id: "openai", label: "OpenAI", model: "gpt-4o-mini", available: true },
                { id: "gemini", label: "Google Gemini", model: "gemini-2.0-flash", available: false },
              ]
            ).map((p) => (
              <option key={p.id} value={p.id} disabled={!p.available}>
                Text: {p.label}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={preset}
            onChange={(e) => setPreset(e.target.value)}
            disabled={busy}
          >
            {(modelsPayload?.presets || [{ id: "linkedin_landscape", width: 1920, height: 1005 }]).map(
              (p) => (
                <option key={p.id} value={p.id}>
                  {p.id.replace("linkedin_", "")} ({p.width}×{p.height})
                </option>
              ),
            )}
          </select>
          <select
            className={cn(selectClass, "sm:max-w-40")}
            value={imageModel}
            onChange={(e) => setImageModel(e.target.value)}
            disabled={busy}
          >
            {(modelsPayload?.models || []).map((m) => (
              <option key={m.id} value={m.id} disabled={!m.available}>
                {m.label}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={renderMode}
            onChange={(e) => setRenderMode(e.target.value as "template" | "native_text")}
            disabled={busy}
          >
            <option value="template">Template overlay</option>
            <option value="native_text">Native text</option>
          </select>
        </div>
      </header>

      <div
        className="lg:hidden shrink-0 grid grid-cols-3 gap-1 rounded-2xl border border-border/80 bg-background/40 p-1"
        role="tablist"
        aria-label="Agent panes"
      >
        {(
          [
            { id: "chats" as const, label: "Chats" },
            { id: "brief" as const, label: "Brief" },
            { id: "artifacts" as const, label: "Artifacts" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={mobilePane === tab.id}
            className={cn(
              "min-h-11 rounded-xl text-xs font-medium transition-colors",
              mobilePane === tab.id
                ? "bg-primary text-primary-foreground shadow-glow"
                : "text-muted-foreground hover:bg-muted/70",
            )}
            onClick={() => setMobilePane(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-[200px_minmax(0,1.1fr)_minmax(0,0.95fr)] gap-3 flex-1 min-h-0 overflow-hidden">
        <aside
          className={cn(
            "min-h-0 flex-col gap-2 overflow-hidden rounded-2xl border border-border/80 bg-background/30 p-2",
            mobilePane === "chats" ? "flex" : "hidden",
            "lg:flex",
          )}
        >
          <div className="flex items-center justify-between px-1 shrink-0">
            <span className="text-xs font-medium flex items-center gap-1.5 text-muted-foreground">
              <History className="h-3.5 w-3.5" />
              Chats
            </span>
            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={newChat}>
              <MessageSquarePlus className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto space-y-1 pr-0.5">
            {sessions.map((s) => (
              <button
                key={s.sessionId}
                type="button"
                onClick={() => {
                  void openSession(s.sessionId)
                  setMobilePane("brief")
                }}
                className={cn(
                  "w-full text-left rounded-xl px-2.5 py-2 text-[11px] border border-transparent hover:bg-muted/80 transition-colors",
                  sessionId === s.sessionId && "bg-primary/12 border-primary/25",
                )}
              >
                <div className="line-clamp-2 font-medium leading-snug">
                  {s.title || `Chat #${s.sessionId}`}
                </div>
              </button>
            ))}
            {!sessions.length && (
              <p className="text-[11px] text-muted-foreground px-1">No chats yet.</p>
            )}
          </div>
        </aside>

        <section
          className={cn(
            "relative min-h-0 flex-col gap-2 overflow-hidden rounded-2xl border border-border/80 bg-background/40",
            mobilePane === "brief" ? "flex" : "hidden",
            "lg:flex",
          )}
        >
          <div className="shrink-0 border-b border-border/60 px-3 py-2 space-y-2">
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="relative flex-1 min-w-0">
                <Link2 className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  className="h-11 sm:h-8 w-full rounded-lg border border-border bg-background/70 pl-8 pr-2 text-xs"
                  placeholder="Repurpose from URL…"
                  value={repurposeUrl}
                  onChange={(e) => setRepurposeUrl(e.target.value)}
                  disabled={busy}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void onRepurposeUrl()
                  }}
                />
              </div>
              <div className="flex gap-2 shrink-0">
              <Button
                size="sm"
                className="h-11 sm:h-8 flex-1 sm:flex-none"
                variant="secondary"
                disabled={busy || !repurposeUrl.trim()}
                onClick={() => void onRepurposeUrl()}
              >
                Go
              </Button>
              <Button
                size="sm"
                className="h-11 sm:h-8 flex-1 sm:flex-none"
                variant="outline"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <FileUp className="h-3.5 w-3.5" />
                PDF
              </Button>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) onRepurposePdf(f)
                  e.target.value = ""
                }}
              />
            </div>
            {stagedPdf && !busy && (
              <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-2 py-1.5 text-[11px]">
                <FileUp className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="truncate flex-1">
                  Attached: {stagedPdf.title || stagedPdf.name}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                  onClick={() => {
                    setStagedPdf(null)
                    setDraftNotice(null)
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            )}
            {stagedUrl && !busy && (
              <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-2 py-1.5 text-[11px]">
                <Link2 className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="truncate flex-1">
                  Attached: {stagedUrl.title || stagedUrl.url}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                  onClick={() => {
                    setStagedUrl(null)
                    setDraftNotice(null)
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            )}
            {pendingPdf && !busy && (
              <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-2 py-1.5 text-[11px]">
                <FileUp className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="truncate flex-1">{pendingPdf.name}</span>
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-6 text-[10px] px-2"
                  onClick={() => void runPdf(pendingPdf.file)}
                >
                  <RotateCcw className="h-3 w-3" />
                  Retry PDF
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0"
                  onClick={() => {
                    setPendingPdf(null)
                    setDraftNotice(null)
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            )}
            {extracting && (
              <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin" />
                Extracting attachment…
              </p>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-2.5">
            <AnimatePresence initial={false}>
              {messages.map((m, i) => (
                <motion.div
                  key={`${i}-${m.role}-${m.content.slice(0, 16)}`}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
                    m.role === "user"
                      ? "ml-auto bg-primary text-primary-foreground"
                      : "mr-auto bg-muted/80",
                  )}
                >
                  {m.content}
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={chatEndRef} />
          </div>

          <div className="shrink-0 border-t border-border/60 p-3 space-y-2 bg-background/50">
            {draftNotice && !busy && (
              <p className="text-xs text-primary">{draftNotice}</p>
            )}
            {genError && !busy && <p className="text-xs text-destructive">{genError}</p>}
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={PLACEHOLDER_SEND}
              disabled={busy || extracting}
              className="min-h-18 max-h-30 resize-none text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  void send()
                }
              }}
            />
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-[10px] text-muted-foreground uppercase tracking-wide">
                Format
              </label>
              <select
                className="h-7 rounded-md border border-border bg-background px-2 text-xs"
                value={postFormat}
                disabled={busy}
                onChange={(e) =>
                  setPostFormat(e.target.value as "text" | "image" | "carousel")
                }
              >
                <option value="image">Image graphic</option>
                <option value="text">Research text</option>
                <option value="carousel">Carousel</option>
              </select>
              {postFormat === "text" && (
                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <input
                    type="checkbox"
                    className="rounded border-border"
                    checked={attachImage}
                    disabled={busy}
                    onChange={(e) => setAttachImage(e.target.checked)}
                  />
                  Attach image
                </label>
              )}
              <div className="flex gap-2 flex-1 justify-end">
                <Button
                  onClick={() => void send()}
                  disabled={
                    chatState.isLoading ||
                    busy ||
                    extracting ||
                    (!(stagedPdf || stagedUrl) && !input.trim())
                  }
                  className="min-w-[88px]"
                  size="sm"
                >
                  Send
                </Button>
                {busy ? (
                  <Button
                    variant="destructive"
                    size="sm"
                    className="gap-1.5 min-w-[110px]"
                    onClick={cancelGenerate}
                  >
                    <Square className="h-3 w-3 fill-current" />
                    Stop
                  </Button>
                ) : (
                  <Button variant="secondary" size="sm" onClick={() => void onGenerate()}>
                    {postFormat === "carousel"
                      ? "Generate carousel"
                      : postFormat === "text"
                        ? "Generate research posts"
                        : "Generate"}
                  </Button>
                )}
              </div>
            </div>
          </div>

          <AnimatePresence>
            {busy && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-20 flex items-center justify-center bg-background/75 backdrop-blur-md p-6"
              >
                <div className="w-full max-w-sm rounded-2xl border border-primary/25 bg-card/95 p-5 shadow-elevated space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      {stageLabel}
                    </div>
                    <div className="flex items-center gap-1 text-sm tabular-nums text-primary">
                      <Clock className="h-3.5 w-3.5" />
                      {formatElapsed(elapsed)}
                    </div>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <motion.div
                      className="h-full bg-primary/80 rounded-full"
                      animate={{ width: `${Math.min(92, 12 + elapsed * 1.1)}%` }}
                      transition={{ ease: "linear", duration: 0.25 }}
                    />
                  </div>
                  <ol className="space-y-1 text-[11px] text-muted-foreground">
                    {GEN_STAGES.map((s, i) => (
                      <li
                        key={s.label}
                        className={cn(i <= stageIndex ? "text-foreground" : "opacity-40")}
                      >
                        {i < stageIndex ? "✓" : i === stageIndex ? "●" : "○"} {s.label}
                      </li>
                    ))}
                  </ol>
                  <Button
                    variant="destructive"
                    className="w-full gap-2"
                    onClick={cancelGenerate}
                  >
                    <Square className="h-3.5 w-3.5 fill-current" />
                    Stop generating
                  </Button>
                  <p className="text-[11px] text-muted-foreground text-center">
                    Your draft message / URL / PDF will be preserved.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        <section
          className={cn(
            "min-h-0 flex-col overflow-hidden rounded-2xl border border-border/80 bg-background/30",
            mobilePane === "artifacts" ? "flex" : "hidden",
            "lg:flex",
          )}
        >
          <div className="shrink-0 flex items-center justify-between gap-2 px-3 py-2 border-b border-border/60">
            <div>
              <h2 className="font-display text-lg leading-tight">Artifacts</h2>
              {batches.length > 0 && (
                <p className="text-[10px] text-muted-foreground">
                  {batches.length} batch{batches.length === 1 ? "" : "es"} · {posts.length} posts
                </p>
              )}
            </div>
            {batchId && (batches.find((b) => b.batchId === batchId)?.posts.length || 0) >= 2 && (
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px] px-2"
                  disabled={scoreBatchState.isLoading}
                  onClick={() => void onScoreAll()}
                >
                  <Gauge className="h-3 w-3" />
                  Score
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px] px-2"
                  disabled={abState.isLoading}
                  onClick={() => void onSuggestSchedule(false)}
                >
                  <Sparkles className="h-3 w-3" />
                  A/B
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-7 text-[11px] px-2"
                  disabled={abState.isLoading}
                  onClick={() => void onSuggestSchedule(true)}
                >
                  Apply
                </Button>
              </div>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-4">
            {strategy && (
              <div className="rounded-xl border border-border bg-muted/40 p-2.5 text-[11px] space-y-1.5">
                <p className="font-medium">A/B plan (latest batch)</p>
                <p className="text-muted-foreground">{strategy}</p>
                <ul className="space-y-0.5">
                  {suggestions.map((s) => (
                    <li key={`${s.label}-${s.postId}`}>
                      <span className="text-primary font-medium">{s.label}</span> · #{s.postId} ·{" "}
                      {s.scheduledAt ? new Date(s.scheduledAt).toLocaleString() : "hold"}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {displayBatches.map((batch, bi) => (
              <div key={batch.batchId || bi} className="space-y-2">
                <div className="flex items-center justify-between gap-2 sticky top-0 z-[1] bg-background/90 backdrop-blur-sm py-1">
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium truncate">
                      Batch #{batch.batchId}
                      {bi === 0 ? " · latest" : ""}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {batch.createdAt
                        ? new Date(batch.createdAt).toLocaleString()
                        : "This session"}
                      {batch.brief ? ` · ${batch.brief.slice(0, 80)}` : ""}
                    </p>
                  </div>
                  {batch.batchId !== batchId && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 text-[10px] shrink-0"
                      onClick={() => setBatchId(batch.batchId)}
                    >
                      Focus
                    </Button>
                  )}
                </div>
                <div className="space-y-3">
                  {(batch.posts || []).map((p) => (
                    <PostCard
                      key={p.postId}
                      p={p}
                      scoring={scoreState.isLoading}
                      posting={quickPublishState.isLoading}
                      onScore={(id) => void onScore(id)}
                      onPostLinkedIn={(id) => void onPostLinkedIn(id)}
                    />
                  ))}
                </div>
              </div>
            ))}

            {!displayBatches.length && !busy && (
              <div className="h-full min-h-[200px] flex items-center justify-center text-center px-6">
                <p className="text-sm text-muted-foreground">
                  All generated creatives for this chat appear here.
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
