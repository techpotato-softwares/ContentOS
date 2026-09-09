import type { Metadata } from "next";
import Link from "next/link";
import { appLoginUrl } from "@/lib/appUrl";
import { FaqAccordion } from "@/components/FaqAccordion";
import { PageHero } from "@/components/PageHero";
import { MarketingCTA } from "@/components/MarketingCTA";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Pricing",
  description: "ContentOS plans for teams, agencies, and growing brands. Start free to get going.",
};

const plans = [
  {
    name: "Starter",
    price: "Contact us",
    description: "For founders and small teams shipping a personal or company brand.",
    features: [
      "1 brand workspace",
      "Brand training + agent chat",
      "Draft captions & carousels",
      "Human review queue",
      "LinkedIn publish & schedule",
    ],
    cta: "Start Free",
    highlighted: false,
  },
  {
    name: "Team",
    price: "Contact us",
    badge: "Most popular",
    description: "For in-house marketers who need roles, insights, and consistent cadence.",
    features: [
      "Everything in Starter",
      "Content insights & analytics",
      "Roles for editors & approvers",
      "Shared review workflows",
      "Priority onboarding",
    ],
    cta: "Start Free",
    highlighted: true,
  },
  {
    name: "Agency",
    price: "Contact us",
    description: "For agencies running many client LinkedIn programs from one OS.",
    features: [
      "Everything in Team",
      "Multi-tenant client workspaces",
      "White-label ready options",
      "Scaled seat management",
      "Dedicated success support",
    ],
    cta: "Talk to sales",
    highlighted: false,
  },
];

const faqs = [
  {
    q: "Is pricing public?",
    a: "Launch plans are flexible while we finalize packaging. Start free and we'll map the right tier to your volume and team size.",
  },
  {
    q: "Do posts publish automatically?",
    a: "No. Human approval is required before anything goes live. Autopilot means drafting and cadence — not unsupervised posting.",
  },
  {
    q: "Can we start with one brand and expand?",
    a: "Yes. Most teams begin with a single workspace, then add brands or client tenants as they scale.",
  },
  {
    q: "What's included in a demo?",
    a: "A 20-minute walkthrough of train → generate → review → publish with your brand context, plus a recommended plan.",
  },
];

export default function PricingPage() {
  return (
    <>
      <PageHero
        eyebrow="Pricing"
        title="Plans that grow with your LinkedIn operation."
        description="Every plan starts free so you can size the workspace to your brands, seats, and posting volume — then pick the right tier."
        primaryCta={{ href: appLoginUrl(), label: "Start Free" }}
        secondaryCta={{ href: "/features", label: "See features" }}
      />

      <section className="border-b border-[var(--line)] bg-[rgba(22,35,31,0.4)]">
        <div className="section-inner grid gap-4 px-5 py-6 text-center text-sm text-steel sm:grid-cols-3 md:px-6">
          <p className="flex items-center justify-center gap-2">
            <span className="trust-chip-dot" />
            Human approval required
          </p>
          <p className="flex items-center justify-center gap-2">
            <span className="trust-chip-dot" />
            Free to start
          </p>
          <p className="flex items-center justify-center gap-2">
            <span className="trust-chip-dot" />
            Built for teams & agencies
          </p>
        </div>
      </section>

      <section className="section">
        <div className="section-inner grid gap-6 lg:grid-cols-3">
          {plans.map((plan, i) => (
            <Reveal key={plan.name} delay={i * 80}>
              <article
                className={`hover-lift relative flex h-full flex-col rounded-2xl border p-7 ${
                  plan.highlighted
                    ? "border-accent bg-surface shadow-[0_18px_40px_rgba(0,0,0,0.35)] lg:-translate-y-2"
                    : "border-[var(--line)] bg-surface/70"
                }`}
              >
                {plan.badge && (
                  <span className="absolute -top-3 left-6 rounded-md bg-accent px-2.5 py-1 text-[11px] font-bold text-[#042f2a]">
                    {plan.badge}
                  </span>
                )}
                <p className="text-sm font-semibold uppercase tracking-wide text-accent">{plan.name}</p>
                <p className="display mt-3 text-3xl text-ink">{plan.price}</p>
                <p className="mt-3 text-sm leading-relaxed text-steel">{plan.description}</p>
                <ul className="mt-6 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex gap-3 text-sm text-ink-soft">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  href={plan.cta === "Talk to sales" ? "/contact" : appLoginUrl()}
                  className={
                    plan.highlighted
                      ? "btn-primary btn-demo mt-8"
                      : plan.cta === "Start Free"
                        ? "btn-secondary btn-demo mt-8"
                        : "btn-secondary mt-8"
                  }
                >
                  {plan.cta}
                </Link>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="section section-band border-t border-[var(--line)]">
        <div className="section-inner max-w-3xl">
          <Reveal>
            <h2 className="display text-3xl text-ink">Billing FAQs</h2>
          </Reveal>
          <div className="mt-10">
            <FaqAccordion items={faqs} />
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Not sure which plan fits?"
        description="Tell us your brands, seats, and LinkedIn cadence — we'll recommend the right workspace."
        secondary={null}
      />
    </>
  );
}
