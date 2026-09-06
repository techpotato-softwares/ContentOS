"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { pathsMatch } from "@/lib/paths";

export function StickyDemoCTA() {
  const pathname = usePathname();
  const [show, setShow] = useState(false);
  const hideOnContact = pathsMatch(pathname, "/contact");

  useEffect(() => {
    if (hideOnContact) {
      setShow(false);
      return;
    }
    const onScroll = () => setShow(window.scrollY > 480);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [hideOnContact]);

  if (hideOnContact) return null;

  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-50 px-4 pb-4 transition-all duration-300 md:hidden ${
        show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-6 opacity-0"
      }`}
    >
      <div className="mx-auto flex max-w-lg items-center gap-3 rounded-xl border border-accent/30 bg-[rgba(7,17,14,0.96)] p-3 shadow-[0_-8px_40px_rgba(0,0,0,0.5),0_0_24px_rgba(62,233,201,0.08)] backdrop-blur-xl">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-ink">Ship on-brand this week</p>
          <p className="truncate text-[11px] text-steel">20-min demo · no credit card</p>
        </div>
        <Link href="/contact" className="btn-primary btn-demo shrink-0 !px-3.5 !py-2.5 !text-xs">
          Book a demo
        </Link>
      </div>
    </div>
  );
}
