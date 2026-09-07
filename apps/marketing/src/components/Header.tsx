"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { pathsMatch } from "@/lib/paths";

const links = [
  { href: "/product", label: "Product" },
  { href: "/features", label: "Features" },
  { href: "/use-cases", label: "Use cases" },
  { href: "/about", label: "About" },
];

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <header
      className={`sticky top-0 z-40 border-b transition-all duration-300 ${
        scrolled
          ? "border-[var(--line)] bg-[rgba(7,17,14,0.92)] shadow-[0_8px_30px_rgba(0,0,0,0.3)] backdrop-blur-xl"
          : "border-transparent bg-[rgba(7,17,14,0.5)] backdrop-blur-md"
      }`}
    >
      <div className="mx-auto flex max-w-[1120px] items-center justify-between px-5 py-3.5 md:px-6 md:py-4">
        <Link
          href="/"
          className="display text-xl tracking-tight text-ink transition hover:opacity-85"
          onClick={() => setOpen(false)}
        >
          Content<span className="text-accent">OS</span>
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
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

        <div className="hidden items-center gap-4 md:flex">
          <Link href="/pricing" className="nav-link text-sm font-medium">
            Pricing
          </Link>
          <Link href="/contact" className="btn-primary btn-demo !px-4 !py-2.5 !text-sm">
            Book a demo
          </Link>
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-[var(--line)] transition hover:border-accent/50 hover:bg-accent-soft/40 md:hidden"
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
        <div className="border-t border-[var(--line)] bg-paper/95 px-5 py-4 backdrop-blur-md md:hidden">
          <nav className="flex flex-col gap-1">
            {links.map((link) => {
              const active = pathsMatch(pathname, link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`nav-link-mobile text-base font-medium ${active ? "is-active" : ""}`}
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </Link>
              );
            })}
            <Link
              href="/contact"
              className="btn-primary btn-demo mt-3"
              onClick={() => setOpen(false)}
            >
              Book a demo
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
