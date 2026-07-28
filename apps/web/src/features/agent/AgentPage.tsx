import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { MessageSquarePlus, History } from "lucide-react"
import {
  useChatMutation,
  useGenerateMutation,
  useListSessionsQuery,
  useLazyGetSessionMessagesQuery,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/input"
import { PostMedia } from "@/shared/ui/PostMedia"
import { cn } from "@/shared/lib/utils"

type Msg = { role: "user" | "assistant"; content: string }

export function AgentPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Tell me what LinkedIn image post you want — informative product graphic, industry news take, celebration post, etc. Company training keeps brand consistent. Then click Generate 3 variants.",
    },
  ])
  const [input, setInput] = useState("")
  const [sessionId, setSessionId] = useState<number | undefined>()
  const [chat, chatState] = useChatMutation()
  const [generate, genState] = useGenerateMutation()
  const { data: sessions = [], refetch: refetchSessions } = useListSessionsQuery()
  const [loadMessages] = useLazyGetSessionMessagesQuery()
  const [posts, setPosts] = useState<
    { postId: number; angle: string; caption: string; imageUrl?: string; status: string }[]
  >([])

  useEffect(() => {
    const prefill = searchParams.get("brief")
    const news = searchParams.get("news")
    if (prefill) {
      setInput(prefill + (news ? `\n\nUse this industry context:\n${news}` : ""))
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

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
    try {
      const res = await generate({ brief, sessionId }).unwrap()
      setPosts(res.posts)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Generated ${res.posts.length} variants (batch #${res.batchId}). View or download below, then open Review to approve.`,
        },
      ])
      void refetchSessions()
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Generation failed — check OpenAI image quota/model, then retry.",
        },
      ])
    }
  }

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
            Briefs → branded informative LinkedIn graphics. Use Insights for domain ideas & news context.
          </p>
        </div>
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
          placeholder="e.g. Informative post: streamline contract lifecycle management with headline, features, and contact footer…"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
        />
        <div className="flex gap-2">
          <Button onClick={() => void send()} disabled={chatState.isLoading} className="flex-1">
            Send
          </Button>
          <Button variant="secondary" onClick={() => void onGenerate()} disabled={genState.isLoading}>
            {genState.isLoading ? "Generating…" : "Generate 3 variants"}
          </Button>
        </div>
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
                <PostMedia
                  imageUrl={p.imageUrl}
                  filename={`contentos-post-${p.postId}.png`}
                />
                <div className="px-4 pb-4 space-y-2">
                  <div className="text-xs uppercase tracking-wide text-primary">{p.angle}</div>
                  <p className="text-sm whitespace-pre-wrap">{p.caption}</p>
                  <div className="text-xs text-muted-foreground">
                    #{p.postId} · {p.status}
                  </div>
                </div>
              </motion.article>
            ))}
          </AnimatePresence>
          {!posts.length && (
            <p className="text-sm text-muted-foreground">Generated posts will appear here with View / Download.</p>
          )}
        </div>
      </div>
    </div>
  )
}
