import Link from "next/link";
import { appLoginUrl } from "@/lib/appUrl";

export function MarketingCTA({
  eyebrow = "Start shipping",
  title = "No more blank-page Mondays.",
  description = "See ContentOS draft on-brand LinkedIn posts for your company — then decide if it belongs in your stack.",
  primary = { href: appLoginUrl(), label: "Start Free" },
  secondary = { href: "/pricing", label: "View plans" },
}: {
  eyebrow?: string;
  title?: string;
  description?: string;
  primary?: { href: string; label: string };
  secondary?: { href: string; label: string } | null;
}) {
  return (
    <section className="section border-t border-[var(--line)]">
      <div className="section-inner relative overflow-hidden rounded-[1.75rem] bg-gradient-to-br from-[#14b8a0] via-[#0d7a6c] to-[#042f2a] px-6 py-14 text-white shadow-[0_30px_80px_rgba(0,0,0,0.35)] md:px-12 md:py-16">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-[#5ff0d4]/25 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-20 left-10 h-40 w-40 rounded-full bg-[rgba(212,180,131,0.2)] blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
            maskImage: "linear-gradient(180deg, rgba(0,0,0,0.55), transparent)",
          }}
          aria-hidden
        />
        <div className="cta-shine pointer-events-none absolute inset-0" aria-hidden />
        <p className="relative text-xs font-semibold uppercase tracking-[0.16em] text-white/70">
          {eyebrow}
        </p>
        <h2 className="relative display mt-3 max-w-2xl text-3xl md:text-5xl">{title}</h2>
        <p className="relative mt-4 max-w-xl text-base leading-relaxed text-white/85 md:text-lg">
          {description}
        </p>
        <div className="relative mt-8 flex flex-wrap items-center gap-3">
          <Link
            href={primary.href}
            className="btn-demo btn-demo-light inline-flex items-center justify-center rounded-xl bg-white px-5 py-3 text-sm font-semibold text-[#0a5c52] transition hover:bg-[#e8fff9] hover:text-[#042f2a]"
          >
            {primary.label}
          </Link>
          {secondary && (
            <Link
              href={secondary.href}
              className="inline-flex items-center justify-center rounded-xl border border-white/35 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              {secondary.label}
            </Link>
          )}
        </div>
        <div className="relative mt-8 flex flex-wrap gap-2">
          {["No credit card", "Human approval always on", "Teams · agencies · founders"].map(
            (item) => (
              <span
                key={item}
                className="rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 text-xs font-medium text-white/90"
              >
                {item}
              </span>
            ),
          )}
        </div>
      </div>
    </section>
  );
}
