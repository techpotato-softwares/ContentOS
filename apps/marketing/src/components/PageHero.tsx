import Link from "next/link";
import { HeroAtmosphere } from "@/components/MarketingImage";

type Cta = { href: string; label: string };

export function PageHero({
  eyebrow,
  title,
  description,
  primaryCta,
  secondaryCta,
}: {
  eyebrow: string;
  title: string;
  description: string;
  primaryCta?: Cta;
  secondaryCta?: Cta;
}) {
  return (
    <section className="relative overflow-hidden border-b border-[var(--line)]">
      <HeroAtmosphere opacity={0.3} />
      <div className="grid-overlay absolute inset-0" aria-hidden />
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_80%_at_0%_0%,rgba(62,233,201,0.2),transparent_55%),radial-gradient(ellipse_50%_60%_at_100%_20%,rgba(95,240,212,0.1),transparent_50%),radial-gradient(ellipse_40%_40%_at_80%_90%,rgba(212,180,131,0.06),transparent_50%)]"
        aria-hidden
      />
      <div className="section-inner relative px-5 py-16 md:px-6 md:py-24">
        <p className="eyebrow animate-rise">{eyebrow}</p>
        <h1 className="display animate-rise-delay-1 mt-3 max-w-3xl text-4xl text-ink md:text-5xl lg:text-[3.25rem]">
          {title}
        </h1>
        <p className="animate-rise-delay-2 mt-5 max-w-2xl text-lg leading-relaxed text-steel">
          {description}
        </p>
        {(primaryCta || secondaryCta) && (
          <div className="animate-rise-delay-3 mt-9 flex flex-wrap gap-3">
            {primaryCta && (
              <Link href={primaryCta.href} className="btn-primary btn-demo">
                {primaryCta.label}
              </Link>
            )}
            {secondaryCta && (
              <Link href={secondaryCta.href} className="btn-secondary">
                {secondaryCta.label}
              </Link>
            )}
          </div>
        )}
        <div className="animate-rise-delay-3 mt-7 flex flex-wrap gap-2">
          <span className="trust-chip">
            <span className="trust-chip-dot" />
            Human approval
          </span>
          <span className="trust-chip">
            <span className="trust-chip-dot" />
            Brand-trained AI
          </span>
          <span className="trust-chip">
            <span className="trust-chip-dot" />
            Free to start
          </span>
        </div>
      </div>
    </section>
  );
}
