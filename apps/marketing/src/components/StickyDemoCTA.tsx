"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { pathsMatch } from "@/lib/paths";
import { appLoginUrl } from "@/lib/appUrl";

export function StickyDemoCTA() {
  const pathname = usePathname();
  const [show, setShow] = useState(false);
  const hideOnContact = pathsMatch(pathname, "/contact");

  useEffect(() => {
    if (hideOnContact) {
      setShow(false);
      return;
    }

    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        setShow(window.scrollY > 480);
      });
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, [hideOnContact]);

  if (hideOnContact) return null;

  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-50 px-4 pb-4 transition-[opacity,transform] duration-300 md:hidden ${
        show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-6 opacity-0"
      }`}
    >
      <div className="mx-auto flex max-w-lg items-center gap-3 rounded-2xl border border-accent/35 bg-[rgba(7,17,14,0.98)] p-3.5 shadow-[0_-10px_44px_rgba(0,0,0,0.55),0_0_28px_rgba(62,233,201,0.1)]">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-ink">Ship on-brand this week</p>
          <p className="truncate text-[11px] text-steel">Free to start · no credit card</p>
        </div>
        <Link
          href={appLoginUrl()}
          className="btn-primary btn-demo shrink-0 !rounded-xl !px-3.5 !py-2.5 !text-xs"
        >
          Start Free
        </Link>
      </div>
    </div>
  );
}
