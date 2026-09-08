import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/PageHero";
import { DraftStudio } from "@/components/DraftStudio";
import { MarketingCTA } from "@/components/MarketingCTA";
import { PipelineVisual } from "@/components/PipelineVisual";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Product",
  description:
    "How ContentOS works: train your brand, get insights, generate drafts, review, and publish to LinkedIn.",
};

const flow = [
  {
    title: "Train the AI on your company",
    copy: "Upload brand voice, colors, domain expertise, and offerings. ContentOS builds a living profile the agent uses for every draft.",
  },
  {
    title: "Review content insights",
    copy: "Optional but powerful: surface themes and angles worth posting so planning takes minutes, not hours.",
  },
  {
    title: "Generate drafts with the agent",
    copy: "Chat with the agent to brief posts. Get captions plus images or carousels that already match your brand.",
  },
  {
    title: "Review and approve",
    copy: "Nothing goes live automatically. Your team edits, rejects, or approves — human-in-the-loop by design.",
  },
  {
    title: "Publish to LinkedIn",
    copy: "Schedule or publish when ready. Less time on research and design; more consistent reach.",
  },
];

export default function ProductPage() {
  return (
    <>
      <PageHero
        eyebrow="Product"
        title="From brand training to LinkedIn publish — one operating system."
        description="ContentOS turns LinkedIn from a weekly scramble into a repeatable loop: train once, generate on-brand drafts, approve with your team, then ship."
        primaryCta={{ href: "/contact", label: "Request a demo" }}
        secondaryCta={{ href: "/features", label: "Browse features" }}
      />

      <section className="section">
        <div className="section-inner grid items-center gap-12 lg:grid-cols-2">
          <Reveal>
            <div>
              <p className="eyebrow">The loop</p>
              <h2 className="display mt-3 text-3xl text-ink md:text-4xl">
                Train → Insights → Generate → Review → Publish
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-steel">
                The core promise: less time on LinkedIn research and design, more consistent publishing
                and reach — without generic AI voice.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                <span className="trust-chip">
                  <span className="trust-chip-dot" />
                  Live Draft Studio
                </span>
                <span className="trust-chip">
                  <span className="trust-chip-dot" />
                  Approve before publish
                </span>
              </div>
            </div>
          </Reveal>
          <Reveal delay={100}>
            <DraftStudio />
          </Reveal>
        </div>
      </section>

      <section className="section section-band border-t border-[var(--line)] !pt-12">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow mb-8">At a glance</p>
            <PipelineVisual />
          </Reveal>
        </div>
      </section>

      <section className="section border-t border-[var(--line)]">
        <div className="section-inner">
          <ol className="space-y-10">
            {flow.map((step, index) => (
              <Reveal key={step.title} delay={index * 50}>
                <li className="hover-reveal grid gap-4 rounded-lg border border-transparent border-t border-t-[var(--line)] p-4 pt-10 md:grid-cols-[120px_1fr]">
                  <span className="hover-step-num display text-4xl text-accent">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h3 className="text-2xl font-semibold text-ink">{step.title}</h3>
                    <p className="mt-3 max-w-2xl text-base leading-relaxed text-steel">{step.copy}</p>
                  </div>
                </li>
              </Reveal>
            ))}
          </ol>
          <div className="mt-12">
            <Link href="/contact" className="btn-primary btn-demo">
              Book a walkthrough
            </Link>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="See the loop with your brand."
        description="We'll walk train → generate → review → publish using your voice and offerings."
        secondary={{ href: "/features", label: "Browse features" }}
      />
    </>
  );
}
