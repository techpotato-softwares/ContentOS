"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { pathsMatch } from "@/lib/paths";
import { appLoginUrl } from "@/lib/appUrl";

const links = [
  { href: "/product", label: "Product" },
  { href: "/features", label: "Features" },
  { href: "/use-cases", label: "Use cases" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
];

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        setScrolled(window.scrollY > 12);
      });
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <header
      className={`sticky top-0 z-40 border-b transition-[background-color,border-color,box-shadow] duration-200 ${
        scrolled
          ? "border-[var(--line)] bg-[rgba(7,17,14,0.97)] shadow-[0_10px_40px_rgba(0,0,0,0.35)]"
          : "border-transparent bg-[rgba(7,17,14,0.88)]"
      }`}
    >
      <div className="mx-auto flex max-w-[1120px] items-center justify-between gap-4 px-5 py-3.5 md:px-6 md:py-4">
        <Link
          href="/"
          className="display text-xl tracking-tight text-ink transition hover:opacity-85"
          onClick={() => setOpen(false)}
        >
          Content<span className="text-accent">OS</span>
        </Link>

        <nav className="hidden items-center gap-6 lg:gap-7 md:flex">
          {links.map((link) => {
            const active = pathsMatch(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`nav-link text-sm font-medium ${active ? "is-active" : ""}`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link
            href={appLoginUrl({ mode: "login" })}
            className="nav-link text-sm font-medium"
          >
            Sign in
          </Link>
          <Link
            href={appLoginUrl()}
            className="btn-primary btn-demo !rounded-xl !px-4 !py-2.5 !text-sm"
          >
            Start Free
          </Link>
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] bg-surface/40 transition hover:border-accent/50 hover:bg-accent-soft/40 md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="sr-only">Menu</span>
          <div className="flex w-4 flex-col gap-1">
            <span
              className={`block h-0.5 w-full bg-ink transition ${open ? "translate-y-1.5 rotate-45" : ""}`}
            />
            <span className={`block h-0.5 w-full bg-ink transition ${open ? "opacity-0" : ""}`} />
            <span
              className={`block h-0.5 w-full bg-ink transition ${open ? "-translate-y-1.5 -rotate-45" : ""}`}
            />
          </div>
        </button>
      </div>

      {open && (
        <div className="border-t border-[var(--line)] bg-[rgba(7,17,14,0.97)] px-5 py-5 backdrop-blur-xl md:hidden">
          <nav className="flex flex-col gap-1">
            {links.map((link) => {
              const active = pathsMatch(pathname, link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`nav-link-mobile rounded-lg px-2 py-2.5 text-base font-medium ${active ? "is-active" : ""}`}
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </Link>
              );
            })}
            <Link
              href={appLoginUrl({ mode: "login" })}
              className="mt-2 rounded-lg px-2 py-2.5 text-base font-medium text-ink-soft"
              onClick={() => setOpen(false)}
            >
              Sign in
            </Link>
            <Link
              href={appLoginUrl()}
              className="btn-primary btn-demo mt-2"
              onClick={() => setOpen(false)}
            >
              Start Free
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
