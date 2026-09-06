import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/PageHero";
import { MarketingCTA } from "@/components/MarketingCTA";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Company training, AI agent chat, insights, analytics, review & publish, multi-tenant workspaces, and roles.",
};

const features = [
  {
    title: "Company training",
    copy: "Capture voice, palette, offerings, and positioning so every draft starts on-brand — not with a blank prompt.",
    outcome: "Consistent brand voice across every post",
  },
  {
    title: "AI agent chat",
    copy: "Brief posts in natural language. Iterate captions and creative direction without hopping between tools.",
    outcome: "Faster drafting without losing control",
  },
  {
    title: "Content insights",
    copy: "Get guidance on what to post next so your calendar fills with relevant angles, not filler.",
    outcome: "No more blank-page Mondays",
  },
  {
    title: "Analytics",
    copy: "Track what lands with your audience and feed those signals back into the next round of drafts.",
    outcome: "Compounding reach over time",
  },
  {
    title: "Review & publish",
    copy: "A dedicated approval queue keeps humans in control. Edit, request rewrites, schedule, or publish.",
    outcome: "Nothing goes live without a yes",
  },
  {
    title: "Multi-tenant & roles",
    copy: "Agency-friendly workspaces with role-based access so clients, editors, and admins stay in their lanes.",
    outcome: "Scale brands without chaos",
  },
];

const extras = [
  { title: "Brand memory", copy: "Voice and offerings persist across every draft cycle." },
  { title: "Approval gates", copy: "Editors and managers decide — never unsupervised publish." },
  { title: "Calendar rhythm", copy: "Insights keep next week's posts from becoming next month's backlog." },
];

export default function FeaturesPage() {
  return (
    <>
      <PageHero
        eyebrow="Features"
        title="Built for marketers who care about control."
        description="ContentOS is not a one-click spam tool. It is a LinkedIn content OS — brand training, generation, review, and publishing in one place."
        primaryCta={{ href: "/contact", label: "Book a demo" }}
        secondaryCta={{ href: "/pricing", label: "Compare plans" }}
      />

      <section className="border-b border-[var(--line)] bg-[rgba(22,35,31,0.4)]">
        <div className="section-inner grid gap-4 px-5 py-8 sm:grid-cols-3 md:px-6">
          {extras.map((item) => (
            <div key={item.title} className="text-center sm:text-left">
              <p className="text-sm font-semibold text-ink">{item.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-steel">{item.copy}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-inner grid gap-6 md:grid-cols-2">
          {features.map((feature, i) => (
            <Reveal key={feature.title} delay={(i % 2) * 80}>
              <article className="hover-lift glass-card h-full rounded-2xl border border-[var(--line)] p-7">
                <span className="display text-2xl text-accent/30">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h2 className="display mt-3 text-2xl text-ink">{feature.title}</h2>
                <p className="mt-3 text-base leading-relaxed text-steel">{feature.copy}</p>
                <p className="mt-5 border-t border-[var(--line)] pt-4 text-sm font-medium text-accent">
                  {feature.outcome}
                </p>
              </article>
            </Reveal>
          ))}
        </div>
        <div className="section-inner mt-12 flex flex-wrap gap-3">
          <Link href="/contact" className="btn-primary btn-demo">
            Book a demo
          </Link>
          <Link href="/use-cases" className="btn-secondary">
            See who it&apos;s for
          </Link>
        </div>
      </section>

      <MarketingCTA
        title="Ready to evaluate ContentOS?"
        description="Book a walkthrough with your brand context — see train, generate, review, and publish in one session."
        secondary={{ href: "/product", label: "How it works" }}
      />
    </>
  );
}
