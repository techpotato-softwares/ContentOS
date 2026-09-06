import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/PageHero";
import { MarketingCTA } from "@/components/MarketingCTA";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "About",
  description:
    "ContentOS is built by TechPotato Softwares LLP — a practical LinkedIn content operating system for teams.",
};

const principles = [
  {
    title: "Brand first",
    copy: "Generic AI output is a non-starter. Training is the foundation of every draft.",
  },
  {
    title: "Human in the loop",
    copy: "Automation drafts. People approve. Trust is a product requirement.",
  },
  {
    title: "Outcomes over jargon",
    copy: "We speak in publishing cadence and brand consistency — not model architecture.",
  },
];

export default function AboutPage() {
  return (
    <>
      <PageHero
        eyebrow="About"
        title="Built by operators who hate blank-page Mondays."
        description="ContentOS is a product of TechPotato Softwares LLP. We build software that helps teams publish consistently — without handing brand voice over to generic AI."
        primaryCta={{ href: "/contact", label: "Book a demo" }}
        secondaryCta={{ href: "/product", label: "See the product" }}
      />

      <section className="section">
        <div className="section-inner grid gap-10 lg:grid-cols-2 lg:gap-14">
          <Reveal>
            <p className="eyebrow">Mission</p>
            <h2 className="display mt-3 text-3xl text-ink md:text-4xl">
              Less research theater. More on-brand publishing.
            </h2>
            <p className="mt-5 text-lg leading-relaxed text-steel">
              Marketing teams should not spend half the week reinventing LinkedIn posts. ContentOS
              trains on your brand, drafts with an AI agent, and keeps humans in the approval loop —
              so reach grows without voice drift.
            </p>
          </Reveal>
          <Reveal delay={120}>
            <div className="glass-card rounded-2xl border border-[var(--line)] p-8">
              <p className="text-sm font-semibold uppercase tracking-wide text-accent">Company</p>
              <p className="display mt-3 text-2xl text-ink md:text-3xl">TechPotato Softwares LLP</p>
              <p className="mt-4 leading-relaxed text-steel">
                We design B2B products that sit where work actually happens. ContentOS is our
                LinkedIn content operating system for multi-tenant teams, agencies, and founders who
                need consistency without sacrificing control.
              </p>
              <div className="mt-8 grid grid-cols-3 gap-3 border-t border-[var(--line)] pt-6 text-center">
                <div>
                  <p className="display text-xl text-accent">B2B</p>
                  <p className="mt-1 text-[11px] text-steel">Focus</p>
                </div>
                <div>
                  <p className="display text-xl text-accent">HITL</p>
                  <p className="mt-1 text-[11px] text-steel">By design</p>
                </div>
                <div>
                  <p className="display text-xl text-accent">Multi</p>
                  <p className="mt-1 text-[11px] text-steel">Tenant ready</p>
                </div>
              </div>
              <Link href="/contact" className="btn-primary btn-demo mt-8 inline-flex">
                Get in touch
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="section section-band border-t border-[var(--line)]">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow">Principles</p>
            <h2 className="display mt-3 max-w-xl text-3xl text-ink">What we refuse to compromise.</h2>
          </Reveal>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {principles.map((item, i) => (
              <Reveal key={item.title} delay={i * 90}>
                <div className="hover-lift h-full rounded-2xl border border-[var(--line)] bg-surface/70 p-6">
                  <span className="display text-2xl text-accent/30">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-3 text-xl font-semibold text-ink">{item.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-steel">{item.copy}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Build your LinkedIn OS with us."
        description="Book a demo and see how ContentOS fits your team, brands, and weekly cadence."
      />
    </>
  );
}
