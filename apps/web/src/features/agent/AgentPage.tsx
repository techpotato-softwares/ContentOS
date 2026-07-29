import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { MessageSquarePlus, History, Loader2, Clock } from "lucide-react"
import {
  useChatMutation,
  useGenerateMutation,
  useListSessionsQuery,
  useLazyGetSessionMessagesQuery,
  useGetImageModelsQuery,
  type ContentPost,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/input"
import { PostMedia } from "@/shared/ui/PostMedia"
import { cn } from "@/shared/lib/utils"

type Msg = { role: "user" | "assistant"; content: string }

const GEN_STAGES = [
  { afterSec: 0, label: "Planning 3 on-brand variants…" },
  { afterSec: 8, label: "Checking claims against company context…" },
  { afterSec: 18, label: "Generating visual backgrounds…" },
  { afterSec: 45, label: "Composing brand layout + logo…" },
  { afterSec: 75, label: "Almost done — uploading creatives…" },
]

function formatElapsed(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
}

export function AgentPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Tell me what LinkedIn image post you want. We generate AI backgrounds and overlay exact brand text + logo (no spelling drift). Then click Generate 3 variants.",
    },
  ])
  const [input, setInput] = useState("")
  const [sessionId, setSessionId] = useState<number | undefined>()
  const [chat, chatState] = useChatMutation()
  const [generate, genState] = useGenerateMutation()
  const { data: sessions = [], refetch: refetchSessions } = useListSessionsQuery()
  const { data: modelsPayload } = useGetImageModelsQuery()
  const [loadMessages] = useLazyGetSessionMessagesQuery()
  const [posts, setPosts] = useState<ContentPost[]>([])
  const [preset, setPreset] = useState("linkedin_landscape")
  const [renderMode, setRenderMode] = useState<"template" | "native_text">("template")
  const [imageModel, setImageModel] = useState("gpt-image-1")
  const [elapsed, setElapsed] = useState(0)
  const [genError, setGenError] = useState<string | null>(null)

  useEffect(() => {
    if (modelsPayload?.defaultPreset) setPreset(modelsPayload.defaultPreset)
    const firstAvail = modelsPayload?.models?.find((m) => m.available)
    if (firstAvail) setImageModel(firstAvail.id)
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
    if (!genState.isLoading) return
    setElapsed(0)
    const started = Date.now()
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000))
    }, 250)
    return () => window.clearInterval(id)
  }, [genState.isLoading])

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

  const openSession = async (id: number) => {
    const res = await loadMessages(id).unwrap()
    setSessionId(res.sessionId)
    const mapped: Msg[] = res.messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }))
    setMessages(
      mapped.length
        ? mapped
        : [
            {
              role: "assistant",
              content: "Continue this chat or generate LinkedIn variants from your brief.",
            },
          ],
    )
    setPosts([])
  }

  const newChat = () => {
    setSessionId(undefined)
    setPosts([])
    setMessages([
      {
        role: "assistant",
        content: "New chat — describe the LinkedIn informative post you want to generate.",
      },
    ])
  }

  const send = async () => {
    if (!input.trim()) return
    const text = input.trim()
    setInput("")
    setMessages((m) => [...m, { role: "user", content: text }])
    try {
      const res = await chat({ message: text, sessionId }).unwrap()
      setSessionId(res.sessionId)
      setMessages((m) => [...m, { role: "assistant", content: res.reply }])
      void refetchSessions()
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Sorry — chat failed. Check API and try again." },
      ])
    }
  }

  const onGenerate = async () => {
    const brief =
      [...messages].reverse().find((m) => m.role === "user")?.content ||
      input ||
      "Create an informative branded LinkedIn image post for our company"
    setGenError(null)
    try {
      const res = await generate({
        brief,
        sessionId,
        preset,
        renderMode,
        imageModel,
      }).unwrap()
      setPosts(res.posts)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Generated ${res.posts.length} variants in ${formatElapsed(elapsed)} (batch #${res.batchId}, ${res.renderMode || renderMode}). View or download below, then open Review to approve.`,
        },
      ])
      void refetchSessions()
    } catch {
      setGenError(`Generation failed after ${formatElapsed(elapsed)}. Check OpenAI quota/model, then retry.`)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Generation failed — check OpenAI image quota/model, then retry.",
        },
      ])
    }
  }

  const selectedModel = modelsPayload?.models?.find((m) => m.id === imageModel)

  return (
    <div className="grid lg:grid-cols-[220px_1fr_1fr] gap-4 h-full">
      <aside className="space-y-3 min-h-[70vh]">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-display text-lg flex items-center gap-2">
            <History className="h-4 w-4" />
            History
          </h2>
          <Button size="sm" variant="outline" onClick={newChat}>
            <MessageSquarePlus className="h-3.5 w-3.5" />
            New
          </Button>
        </div>
        <div className="space-y-1 overflow-y-auto max-h-[70vh] pr-1">
          {sessions.map((s) => (
            <button
              key={s.sessionId}
              type="button"
              onClick={() => void openSession(s.sessionId)}
              className={cn(
                "w-full text-left rounded-xl px-3 py-2 text-xs border border-transparent hover:bg-muted transition-colors",
                sessionId === s.sessionId && "bg-primary/15 border-primary/30",
              )}
            >
              <div className="line-clamp-2 font-medium">{s.title || `Chat #${s.sessionId}`}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5">
                {s.updatedAt ? new Date(s.updatedAt).toLocaleString() : ""}
              </div>
            </button>
          ))}
          {!sessions.length && (
            <p className="text-xs text-muted-foreground px-1">No chats yet — send a message.</p>
          )}
        </div>
      </aside>

      <div className="flex flex-col gap-4 min-h-[70vh]">
        <div>
          <h1 className="font-display text-3xl">Agent chat</h1>
          <p className="text-sm text-muted-foreground">
            Template overlay (default) prints exact headline + logo — AI paints the background only.
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-2">
          <label className="text-xs space-y-1">
            <span className="text-muted-foreground">Preset</span>
            <select
              className="h-9 w-full rounded-xl border border-border bg-background/60 px-2 text-sm"
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              disabled={genState.isLoading}
            >
              {(modelsPayload?.presets || [{ id: "linkedin_landscape", width: 1200, height: 627 }]).map(
                (p) => (
                  <option key={p.id} value={p.id}>
                    {p.id.replace("linkedin_", "")} ({p.width}×{p.height})
                  </option>
                ),
              )}
            </select>
          </label>
          <label className="text-xs space-y-1">
            <span className="text-muted-foreground">Image model</span>
            <select
              className="h-9 w-full rounded-xl border border-border bg-background/60 px-2 text-sm"
              value={imageModel}
              onChange={(e) => setImageModel(e.target.value)}
              disabled={genState.isLoading}
            >
              {(modelsPayload?.models || []).map((m) => (
                <option key={m.id} value={m.id} disabled={!m.available}>
                  {m.label}
                  {!m.available ? " (unavailable)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs space-y-1">
            <span className="text-muted-foreground">Render mode</span>
            <select
              className="h-9 w-full rounded-xl border border-border bg-background/60 px-2 text-sm"
              value={renderMode}
              onChange={(e) => setRenderMode(e.target.value as "template" | "native_text")}
              disabled={genState.isLoading}
            >
              <option value="template">Template overlay (recommended)</option>
              <option value="native_text">Native text (experimental)</option>
            </select>
          </label>
        </div>
        {selectedModel && (
          <p className="text-[11px] text-muted-foreground -mt-2">
            {selectedModel.bestFor} · native text: {selectedModel.nativeTextQuality} · {selectedModel.costHint}
          </p>
        )}

        <div className="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-border p-4 bg-background/40">
          <AnimatePresence initial={false}>
            {messages.map((m, i) => (
              <motion.div
                key={`${i}-${m.role}-${m.content.slice(0, 12)}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={
                  m.role === "user"
                    ? "ml-8 rounded-2xl bg-primary text-primary-foreground px-4 py-3 text-sm"
                    : "mr-8 rounded-2xl bg-muted px-4 py-3 text-sm"
                }
              >
                {m.content}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Informative post about contract lifecycle management for legal ops…"
          disabled={genState.isLoading}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
        />
        <div className="flex gap-2">
          <Button onClick={() => void send()} disabled={chatState.isLoading || genState.isLoading} className="flex-1">
            Send
          </Button>
          <Button variant="secondary" onClick={() => void onGenerate()} disabled={genState.isLoading}>
            {genState.isLoading ? "Generating…" : "Generate 3 variants"}
          </Button>
        </div>

        {genState.isLoading && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                {stageLabel}
              </div>
              <div className="flex items-center gap-1.5 text-sm tabular-nums text-primary">
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
            <ol className="grid grid-cols-1 gap-1 text-[11px] text-muted-foreground">
              {GEN_STAGES.map((s, i) => (
                <li key={s.label} className={cn(i <= stageIndex ? "text-foreground" : "opacity-50")}>
                  {i < stageIndex ? "✓" : i === stageIndex ? "●" : "○"} {s.label}
                </li>
              ))}
            </ol>
            <p className="text-[11px] text-muted-foreground">
              This usually takes 1–3 minutes (3 image API calls + composition). Keep this tab open.
            </p>
          </div>
        )}
        {genError && !genState.isLoading && (
          <p className="text-sm text-destructive">{genError}</p>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="font-display text-xl">Variants</h2>
        <div className="grid gap-4">
          <AnimatePresence>
            {posts.map((p) => (
              <motion.article
                key={p.postId}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-border overflow-hidden bg-background/50"
              >
                <PostMedia imageUrl={p.imageUrl} filename={`contentos-post-${p.postId}.png`} />
                <div className="px-4 pb-4 space-y-2">
                  <div className="text-xs uppercase tracking-wide text-primary">{p.angle}</div>
                  {(p.headline || p.layout?.headline) && (
                    <h3 className="font-display text-lg leading-snug">
                      {p.headline || p.layout?.headline}
                    </h3>
                  )}
                  {(p.subhead || p.layout?.subhead) && (
                    <p className="text-sm text-muted-foreground">{p.subhead || p.layout?.subhead}</p>
                  )}
                  {(p.bullets || p.layout?.bullets)?.length ? (
                    <ul className="text-xs list-disc pl-4 space-y-0.5">
                      {(p.bullets || p.layout?.bullets || []).map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                  ) : null}
                  <p className="text-sm whitespace-pre-wrap">{p.caption}</p>
                  <div className="text-xs text-muted-foreground">
                    #{p.postId} · {p.status}
                  </div>
                </div>
              </motion.article>
            ))}
          </AnimatePresence>
          {!posts.length && !genState.isLoading && (
            <p className="text-sm text-muted-foreground">
              Generated posts will appear here with View / Download.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
