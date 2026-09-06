"use client";

import { useState } from "react";

export function FaqAccordion({
  items,
}: {
  items: { q: string; a: string }[];
}) {
  const [open, setOpen] = useState(0);

  return (
    <div className="space-y-3">
      {items.map((item, i) => {
        const isOpen = open === i;
        return (
          <div
            key={item.q}
            className={`overflow-hidden rounded-xl border transition-colors duration-300 ${
              isOpen
                ? "border-accent/40 bg-accent-soft/30"
                : "border-[var(--line)] bg-surface/50 hover:border-accent/25"
            }`}
          >
            <button
              type="button"
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? -1 : i)}
            >
              <span className="text-base font-semibold text-ink">{item.q}</span>
              <span
                className={`display flex h-7 w-7 shrink-0 items-center justify-center rounded-md border text-sm transition-all duration-300 ${
                  isOpen
                    ? "border-accent/50 bg-accent/15 text-accent rotate-45"
                    : "border-[var(--line)] text-steel"
                }`}
                aria-hidden
              >
                +
              </span>
            </button>
            <div
              className={`grid transition-[grid-template-rows] duration-300 ease-out ${
                isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
              }`}
            >
              <div className="overflow-hidden">
                <p className="px-5 pb-5 text-sm leading-relaxed text-steel">{item.a}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
