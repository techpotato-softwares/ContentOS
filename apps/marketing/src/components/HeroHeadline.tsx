"use client";

import { useEffect, useState, type ReactNode } from "react";

const LINES = [
  "LinkedIn on autopilot — without losing your voice.",
  "Train once. Draft every week. Approve before publish.",
  "On-brand posts in minutes — not blank-page Mondays.",
];

const TYPE_MS = 38;
const HOLD_MS = 2400;
const DELETE_MS = 18;
const GAP_MS = 420;

export function HeroHeadline() {
  const [lineIndex, setLineIndex] = useState(0);
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<"typing" | "holding" | "deleting">("typing");

  const full = LINES[lineIndex];

  useEffect(() => {
    let timer: number;

    if (phase === "typing") {
      if (text.length < full.length) {
        timer = window.setTimeout(() => {
          setText(full.slice(0, text.length + 1));
        }, TYPE_MS);
      } else {
        timer = window.setTimeout(() => setPhase("holding"), 40);
      }
    } else if (phase === "holding") {
      timer = window.setTimeout(() => setPhase("deleting"), HOLD_MS);
    } else if (phase === "deleting") {
      if (text.length > 0) {
        timer = window.setTimeout(() => {
          setText(text.slice(0, -1));
        }, DELETE_MS);
      } else {
        timer = window.setTimeout(() => {
          setLineIndex((i) => (i + 1) % LINES.length);
          setPhase("typing");
        }, GAP_MS);
      }
    }

    return () => window.clearTimeout(timer);
  }, [text, phase, full]);

  const highlight = (value: string) => {
    const keywords = ["autopilot", "voice.", "Approve", "on-brand", "blank-page"];
    const parts: ReactNode[] = [];
    let remaining = value;
    let key = 0;

    while (remaining.length > 0) {
      let bestIdx = -1;
      let bestWord = "";

      for (const word of keywords) {
        const idx = remaining.indexOf(word);
        if (idx !== -1 && (bestIdx === -1 || idx < bestIdx)) {
          bestIdx = idx;
          bestWord = word;
        }
      }

      if (bestIdx === -1) {
        parts.push(<span key={key++}>{remaining}</span>);
        break;
      }

      if (bestIdx > 0) {
        parts.push(<span key={key++}>{remaining.slice(0, bestIdx)}</span>);
      }

      const isVoice = bestWord === "voice.";
      parts.push(
        <span key={key++} className={isVoice ? "hero-running-voice" : "text-accent"}>
          {remaining.slice(bestIdx, bestIdx + bestWord.length)}
        </span>,
      );
      remaining = remaining.slice(bestIdx + bestWord.length);
    }

    return parts;
  };

  return (
    <h1 className="display mt-6 min-h-[3.4em] max-w-[24ch] text-[1.85rem] leading-[1.12] text-ink sm:min-h-[2.6em] sm:text-4xl md:text-[2.55rem]">
      <span className="hero-running">
        {highlight(text)}
        <span className="hero-running-caret" aria-hidden />
      </span>
      <span className="sr-only">{LINES.join(" ")}</span>
    </h1>
  );
}
