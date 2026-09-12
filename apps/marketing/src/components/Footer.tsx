import Link from "next/link";
import { appLoginUrl } from "@/lib/appUrl";

const columns = [
  {
    title: "Product",
    links: [
      { href: "/product", label: "How it works" },
      { href: "/features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    title: "Solutions",
    links: [
      { href: "/use-cases#teams", label: "Marketing teams" },
      { href: "/use-cases#agencies", label: "Agencies" },
      { href: "/use-cases#founders", label: "Founders" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/contact", label: "Contact" },
      { href: appLoginUrl(), label: "Start Free" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative overflow-hidden border-t border-[var(--line)] bg-gradient-to-b from-[#10241c] to-[#050c0a]">
      <div
        className="pointer-events-none absolute inset-0 opacity-35"
        style={{
          backgroundImage: "radial-gradient(rgba(232,238,246,0.06) 0.7px, transparent 0.7px)",
          backgroundSize: "16px 16px",
        }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -top-24 left-1/2 h-56 w-[32rem] -translate-x-1/2 rounded-full bg-accent/12 blur-3xl"
        aria-hidden
      />
      <div className="section-inner relative px-5 py-16 md:px-6 md:py-20">
        <div className="mid-cta-band mb-14 px-6 py-9 md:flex md:items-center md:justify-between md:px-10 md:py-11">
          <div>
            <p className="eyebrow">Ready when you are</p>
            <p className="display mt-2 text-2xl text-ink md:text-3xl">
              Ship on-brand LinkedIn this week.
            </p>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-steel">
              Start free — train, generate, review, and publish in one loop.
            </p>
          </div>
          <div className="mt-6 flex flex-wrap gap-3 md:mt-0">
            <Link href={appLoginUrl()} className="btn-primary btn-demo inline-flex">
              Start Free
            </Link>
            <Link href="/product" className="btn-secondary inline-flex">
              See product
            </Link>
          </div>
        </div>

        <div className="grid gap-12 md:grid-cols-[1.45fr_1fr_1fr_1fr] md:gap-10">
          <div>
            <Link href="/" className="display text-2xl text-ink">
              Content<span className="text-accent">OS</span>
            </Link>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-steel">
              LinkedIn content on autopilot — without losing your voice. Built by TechPotato
              Softwares LLP.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="trust-chip">
                <span className="trust-chip-dot" />
                HITL by design
              </span>
              <span className="trust-chip">
                <span className="trust-chip-dot" />
                Multi-tenant
              </span>
            </div>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-accent/80">
                {col.title}
              </p>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((link) => (
                  <li key={`${col.title}-${link.label}`}>
                    <Link
                      href={link.href}
                      className="text-sm text-steel transition hover:text-ink"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col gap-2 border-t border-[var(--line)] pt-7 text-sm text-steel md:flex-row md:items-center md:justify-between">
          <p>© {new Date().getFullYear()} TechPotato Softwares LLP. All rights reserved.</p>
          <p className="text-ink-soft/70">LinkedIn content operating system for teams.</p>
        </div>
      </div>
    </footer>
  );
}
