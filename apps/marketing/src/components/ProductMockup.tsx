"use client";

import { useEffect, useState } from "react";

const navItems = [
  { id: "chat", label: "Agent chat", icon: "◇" },
  { id: "train", label: "Brand training", icon: "◎" },
  { id: "insights", label: "Insights", icon: "▦" },
  { id: "review", label: "Review queue", icon: "☰" },
  { id: "analytics", label: "Analytics", icon: "▴" },
] as const;

const drafts = [
  {
    brand: "Acme Cloud",
    initials: "AC",
    title: "Weekly LinkedIn draft",
    caption:
      "Most teams don't have a LinkedIn problem — they have a consistency problem. Here's how we ship three posts a week without a blank-page Monday…",
    slides: [
      "Train once. Publish every week.",
      "Voice matched. Palette locked.",
      "Human review before go-live.",
      "Insights that fill the calendar.",
      "Reach without blank-page Mondays.",
    ],
    tags: ["Carousel", "B2B", "Thought leadership"],
  },
  {
    brand: "Northwind Labs",
    initials: "NL",
    title: "Founder voice draft",
    caption:
      "We stopped writing posts from scratch. One brand brief. One approval loop. Reach went up because the calendar finally stayed full.",
    slides: [
      "Your voice. On schedule.",
      "Train the agent once.",
      "Approve in one click.",
      "Ship before coffee cools.",
      "Personal brand, on rails.",
    ],
    tags: ["Founder", "Personal brand", "Image"],
  },
  {
    brand: "Pixel Agency",
    initials: "PA",
    title: "Client workspace draft",
    caption:
      "Managing 12 client LinkedIn pages used to mean 12 blank docs. Now every brand has its own trained agent — and one review queue.",
    slides: [
      "Multi-tenant. Still on-brand.",
      "One OS. Many clients.",
      "Roles for editors & approvers.",
      "Faster turnarounds.",
      "Agency scale without chaos.",
    ],
    tags: ["Agency", "Multi-tenant", "Carousel"],
  },
];

const agentScript = [
  { role: "user" as const, text: "Draft this week's LinkedIn carousel." },
  { role: "agent" as const, text: "Pulling brand voice + palette…" },
  { role: "agent" as const, text: "Writing caption in your tone." },
  { role: "agent" as const, text: "Building 5 slides. Ready for review." },
];

type Status = "generating" | "review" | "ready";

export function ProductMockup({ className = "" }: { className?: string }) {
  const [active, setActive] = useState(false);
  const [draftIndex, setDraftIndex] = useState(0);
  const [typed, setTyped] = useState(drafts[0].caption);
  const [status, setStatus] = useState<Status>("ready");
  const [slide, setSlide] = useState(0);
  const [visibleMsgs, setVisibleMsgs] = useState(agentScript.length);
  const [likes, setLikes] = useState(128);
  const [fade, setFade] = useState(true);
  const [clock, setClock] = useState("--:--");

  const draft = drafts[draftIndex];
  const progress = status === "generating" ? 42 : status === "review" ? 76 : 100;
  const activeNav = status === "generating" ? "chat" : "review";

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const start = () => setActive(true);
    const t = window.setTimeout(start, 1200);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      );
    tick();
    const timer = window.setInterval(tick, 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!active) return;

    setFade(false);
    const t = window.setTimeout(() => setFade(true), 40);
    setTyped("");
    setStatus("generating");
    setSlide(0);
    setVisibleMsgs(1);
    setLikes(110 + draftIndex * 37);

    let char = 0;
    const full = drafts[draftIndex].caption;
    let readyTimer: number | undefined;
    const typeTimer = window.setInterval(() => {
      char += 1;
      setTyped(full.slice(0, char));
      if (char >= full.length) {
        window.clearInterval(typeTimer);
        setStatus("review");
        readyTimer = window.setTimeout(() => setStatus("ready"), 1100);
      }
    }, 28);

    return () => {
      window.clearTimeout(t);
      window.clearInterval(typeTimer);
      if (readyTimer) window.clearTimeout(readyTimer);
    };
  }, [active, draftIndex]);

  useEffect(() => {
    if (!active) return;
    const msgTimer = window.setInterval(() => {
      setVisibleMsgs((n) => (n >= agentScript.length ? n : n + 1));
    }, 1400);
    return () => window.clearInterval(msgTimer);
  }, [active, draftIndex]);

  useEffect(() => {
    if (!active) return;
    const slideTimer = window.setInterval(() => {
      setSlide((s) => (s + 1) % draft.slides.length);
    }, 2200);
    return () => window.clearInterval(slideTimer);
  }, [active, draft.slides.length, draftIndex]);

  useEffect(() => {
    if (!active) return;
    const draftTimer = window.setInterval(() => {
      setDraftIndex((i) => (i + 1) % drafts.length);
    }, 14000);
    return () => window.clearInterval(draftTimer);
  }, [active]);

  useEffect(() => {
    if (!active || status !== "ready") return;
    const likeTimer = window.setInterval(() => {
      setLikes((n) => n + (Math.random() > 0.5 ? 1 : 0));
    }, 1800);
    return () => window.clearInterval(likeTimer);
  }, [active, status]);

  return (
    <div className={`relative mx-auto w-full max-w-[480px] md:max-w-[520px] ${className}`}>
      <div className="studio-aura" aria-hidden>
        <span className="studio-orb studio-orb-a" />
        <span className="studio-orb studio-orb-b" />
        <span className="studio-orb studio-orb-c" />
        <span className="studio-ring" />
      </div>

      <div className="studio-shell relative z-[1] overflow-hidden rounded-xl border border-[var(--line)] bg-[#121c19]/95 shadow-[0_20px_50px_rgba(0,0,0,0.45)]">
        {/* Title bar */}
        <div className="flex items-center justify-between gap-2 border-b border-[var(--line)] bg-[#0d1513] px-3 py-2">
          <div className="flex min-w-0 items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#ff5f57]" />
            <span className="h-2 w-2 rounded-full bg-[#febc2e]" />
            <span className="h-2 w-2 rounded-full bg-[#28c840]" />
            <span className="ml-1.5 truncate text-[11px] font-medium text-steel">
              ContentOS · Draft studio
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="hidden text-[10px] text-steel sm:inline">{clock}</span>
            <span className="studio-live inline-flex items-center gap-1 rounded-full border border-accent/35 bg-accent-soft/70 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-accent">
              <span className="studio-live-dot h-1.5 w-1.5 rounded-full bg-accent" />
              Live
            </span>
          </div>
        </div>

        <div className="grid md:grid-cols-[168px_1fr]">
          {/* Sidebar */}
          <aside className="hidden border-r border-[var(--line)] bg-[#0f1815] p-3 md:flex md:flex-col">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15 text-[10px] font-bold text-accent">
                {draft.initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[11px] font-semibold text-ink">{draft.brand}</p>
                <p className="text-[9px] text-steel">Workspace</p>
              </div>
            </div>

            <ul className="mt-3 space-y-0.5">
              {navItems.map((item) => (
                <li
                  key={item.id}
                  className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[12px] transition-all duration-500 ${
                    activeNav === item.id
                      ? "bg-accent-soft font-medium text-accent shadow-[inset_2px_0_0_var(--accent)]"
                      : "text-ink-soft"
                  }`}
                >
                  <span className="text-[9px] opacity-70">{item.icon}</span>
                  {item.label}
                  {item.id === "review" && (
                    <span className="ml-auto rounded-full bg-accent/20 px-1.5 text-[9px] font-semibold text-accent">
                      3
                    </span>
                  )}
                </li>
              ))}
            </ul>

            <div className="mt-auto pt-3">
              <div className="studio-chat rounded-lg border border-[var(--line)] bg-[#0b1210] p-2.5">
                <div className="mb-1.5 flex items-center justify-between">
                  <p className="text-[9px] font-semibold uppercase tracking-wide text-steel">
                    Agent feed
                  </p>
                  <span className="studio-typing flex gap-0.5">
                    <i />
                    <i />
                    <i />
                  </span>
                </div>
                <div className="flex max-h-[108px] flex-col gap-1.5 overflow-hidden">
                  {agentScript.slice(0, visibleMsgs).map((msg, i) => (
                    <div
                      key={`${draftIndex}-${i}`}
                      className={`studio-msg max-w-[95%] rounded-md px-2 py-1 text-[10px] leading-snug ${
                        msg.role === "user"
                          ? "self-end bg-accent/20 text-ink"
                          : "self-start bg-white/5 text-ink-soft"
                      }`}
                    >
                      {msg.text}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </aside>

          {/* Main canvas */}
          <div
            className={`p-3 transition-opacity duration-500 md:p-3.5 ${fade ? "opacity-100" : "opacity-0"}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <p className="text-[13px] font-semibold text-ink">{draft.title}</p>
                  <span className="rounded border border-[var(--line)] px-1.5 py-0.5 text-[9px] text-steel">
                    v{draftIndex + 1}.0
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-steel">
                  Trained on <span className="text-ink-soft">{draft.brand}</span>
                  {" · "}
                  {status === "generating"
                    ? "Agent writing…"
                    : status === "review"
                      ? "Waiting for approval"
                      : "Ready to publish"}
                </p>
              </div>
              <StatusPill status={status} />
            </div>

            <div className="mt-2.5">
              <div className="mb-1 flex items-center justify-between text-[9px] text-steel">
                <span>Pipeline</span>
                <span>{progress}%</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-white/5">
                <div
                  className="studio-progress h-full rounded-full bg-gradient-to-r from-accent-deep to-accent"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-1.5 flex justify-between text-[9px] text-steel">
                <span className={status !== "generating" ? "text-accent" : ""}>Generate</span>
                <span className={status === "review" || status === "ready" ? "text-accent" : ""}>
                  Review
                </span>
                <span className={status === "ready" ? "text-accent" : ""}>Publish</span>
              </div>
            </div>

            {/* Mobile agent strip */}
            <div className="mt-3 rounded-md border border-[var(--line)] bg-[#0b1210] px-2.5 py-1.5 md:hidden">
              <p className="text-[10px] text-ink-soft">
                {agentScript[Math.min(visibleMsgs, agentScript.length) - 1]?.text}
              </p>
            </div>

            {/* LinkedIn-style post */}
            <div className="mt-3 overflow-hidden rounded-lg border border-[var(--line)] bg-[#0b1210]">
              <div className="flex items-center gap-2 border-b border-[var(--line)] px-3 py-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-deep text-[10px] font-bold text-[#042f2e]">
                  {draft.initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] font-semibold text-ink">{draft.brand}</p>
                  <p className="text-[10px] text-steel">ContentOS · Just now</p>
                </div>
                <div className="flex gap-1">
                  {draft.tags.slice(0, 2).map((tag) => (
                    <span
                      key={tag}
                      className="hidden rounded-full border border-[var(--line)] px-1.5 py-0.5 text-[9px] text-steel sm:inline"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="px-3 py-2">
                <p className="min-h-[3.5rem] text-[12px] leading-relaxed text-ink-soft">
                  {typed}
                  {status === "generating" && <span className="studio-caret" />}
                </p>
              </div>

              <div className="relative mx-3 mb-3 overflow-hidden rounded-lg bg-gradient-to-br from-[#14b8a0] via-[#0d7a6c] to-[#042f2a] p-3.5 text-white">
                <div className="pointer-events-none absolute -right-4 -top-4 h-16 w-16 rounded-full bg-white/10 blur-xl" />
                <div className="mb-2.5 flex gap-1">
                  {draft.slides.map((_, n) => (
                    <span
                      key={n}
                      className={`h-0.5 flex-1 rounded-full transition-all duration-500 ${
                        n === slide ? "bg-white" : "bg-white/25"
                      }`}
                    />
                  ))}
                </div>
                <p
                  key={`${draftIndex}-${slide}`}
                  className="studio-slide-text display text-base leading-snug sm:text-lg"
                >
                  {draft.slides[slide]}
                </p>
                <div className="mt-2.5 flex items-end justify-between gap-2">
                  <p className="text-[10px] text-white/75">
                    Slide {slide + 1}/{draft.slides.length} · Brand palette
                  </p>
                  <p className="text-[9px] uppercase tracking-wider text-white/50">ContentOS</p>
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-[var(--line)] px-3 py-2 text-[10px] text-steel">
                <span>
                  <span className="text-accent">{likes}</span> reactions · preview
                </span>
                <span>{status === "ready" ? "Thu 9:00 AM" : "Not scheduled"}</span>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                className={`btn-primary !px-2.5 !py-1.5 !text-[11px] ${
                  status === "ready" ? "studio-cta-ready" : "opacity-45"
                }`}
              >
                Approve &amp; schedule
              </button>
              <button type="button" className="btn-secondary !px-2.5 !py-1.5 !text-[11px]">
                Request rewrite
              </button>
              <div className="ml-auto flex items-center gap-1.5">
                {drafts.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    aria-label={`Show draft ${i + 1}`}
                    onClick={() => setDraftIndex(i)}
                    className={`h-1.5 rounded-full transition-all ${
                      i === draftIndex ? "w-5 bg-accent" : "w-1.5 bg-white/20 hover:bg-white/40"
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: Status }) {
  const map = {
    generating: {
      label: "Generating",
      className: "bg-[rgba(62,233,201,0.16)] text-accent border-accent/25",
    },
    review: {
      label: "In review",
      className: "bg-[rgba(251,188,46,0.14)] text-[#febc2e] border-[#febc2e]/25",
    },
    ready: {
      label: "On-brand",
      className: "bg-[rgba(62,207,142,0.14)] text-[var(--success)] border-[var(--success)]/25",
    },
  }[status];

  return (
    <span
      className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold transition-colors duration-500 ${map.className}`}
    >
      {map.label}
    </span>
  );
}

export default ProductMockup;
