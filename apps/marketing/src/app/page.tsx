import Link from "next/link";
import { CountUp } from "@/components/CountUp";
import { DraftStudio } from "@/components/DraftStudio";
import { FaqAccordion } from "@/components/FaqAccordion";
import { HeroHeadline } from "@/components/HeroHeadline";
import { MarketingCTA } from "@/components/MarketingCTA";
import { PipelineVisual } from "@/components/PipelineVisual";
import { Reveal } from "@/components/Reveal";
import { WeekCadence } from "@/components/WeekCadence";

const steps = [
  {
    title: "Train",
    copy: "Feed your voice, colors, products, and positioning once — the agent remembers.",
  },
  {
    title: "Insights",
    copy: "See what themes deserve a post this week, so planning is not a guessing game.",
  },
  {
    title: "Generate",
    copy: "Get captions, images, and carousels drafted in minutes — already on-brand.",
  },
  {
    title: "Review",
    copy: "Your team edits or approves. Nothing publishes without a human yes.",
  },
  {
    title: "Publish",
    copy: "Schedule to LinkedIn and keep a cadence your audience can actually feel.",
  },
];

const outcomes = [
  {
    title: "On-brand, not generic",
    copy: "Every draft starts from your trained brand profile — voice, palette, and offerings.",
  },
  {
    title: "Human in the loop",
    copy: "Approve before go-live. Autopilot drafts. You stay in control of the brand.",
  },
  {
    title: "Built for teams",
    copy: "Roles, review queues, and multi-tenant workspaces for agencies and in-house teams.",
  },
  {
    title: "Ship every week",
    copy: "Less blank-page time. More consistent publishing and reach on LinkedIn.",
  },
];

const capabilities = [
  {
    title: "Brand-trained AI agent",
    copy: "Not a blank prompt. Your company voice, colors, and offerings live in the workspace.",
  },
  {
    title: "Captions + carousels",
    copy: "Generate the full post — copy and creative — ready for review in minutes.",
  },
  {
    title: "Approval queue",
    copy: "Editors and managers stay in control. Nothing goes live without a human yes.",
  },
  {
    title: "Insights that fill the calendar",
    copy: "Know what to post next so Mondays stop starting with a blank page.",
  },
  {
    title: "Analytics that compound",
    copy: "See what lands, then feed those signals into the next round of drafts.",
  },
  {
    title: "Multi-tenant for agencies",
    copy: "Run every client brand from one OS — separate workspaces, shared workflow.",
  },
];

const audiences = [
  {
    title: "In-house marketing teams",
    promise: "Post consistently on-brand, in minutes — without waiting on design.",
    proof: "Shared brand training · Editor + approver roles · Insights for the calendar",
    href: "/use-cases#teams",
  },
  {
    title: "Agencies",
    promise: "Run every client's LinkedIn from one multi-tenant operating system.",
    proof: "Separate brand workspaces · Faster turnarounds · White-label ready options",
    href: "/use-cases#agencies",
  },
  {
    title: "Founders & personal brands",
    promise: "Train once on your voice — then approve drafts that still sound like you.",
    proof: "Voice-matched copy · Carousels without a design stack · You approve first",
    href: "/use-cases#founders",
  },
];

const quotes = [
  {
    quote:
      "We stopped losing Mondays to LinkedIn. Drafts arrive on-brand — we just approve and ship.",
    role: "Head of Marketing · B2B SaaS",
  },
  {
    quote:
      "Client LinkedIn used to be spreadsheet chaos. One workspace per brand changed the math.",
    role: "Agency founder",
  },
  {
    quote:
      "It still sounds like me. That was the only non-negotiable — and ContentOS cleared it.",
    role: "Founder · Series A",
  },
];

const objections = [
  {
    q: "Will it sound like generic AI?",
    a: "No. ContentOS is trained on your brand voice first. Every draft starts from your profile — then a human approves before publish.",
  },
  {
    q: "Can posts go live without us?",
    a: "Never by default. Human-in-the-loop is the product. Approve, rewrite, or reject — you decide.",
  },
  {
    q: "Does it work for agencies?",
    a: "Yes. Multi-tenant workspaces let you run every client brand from one OS with roles and review queues.",
  },
  {
    q: "How long does onboarding take?",
    a: "Most teams train a brand profile in one session, then generate the first reviewable drafts the same week.",
  },
];

const logos = ["Acme Cloud", "Northwind", "Pixel Co", "Brightline", "Orbit Labs", "Harbor AI"];

const results = [
  { value: "Minutes", label: "to first on-brand draft" },
  { value: "100%", label: "human approval before publish" },
  { value: "1 OS", label: "for every brand workspace" },
  { value: "Weekly", label: "cadence without burnout" },
];

const demoSteps = [
  { title: "Share your brand", copy: "Voice, offerings, and how you want LinkedIn to sound." },
  { title: "Watch the loop", copy: "Live train → generate → review → publish walkthrough." },
  { title: "Leave with a plan", copy: "Seats, workspace fit, and optional pilot mapped out." },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="grid-overlay absolute inset-0" aria-hidden />
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_65%_70%_at_90%_10%,rgba(62,233,201,0.28),transparent_55%),radial-gradient(ellipse_45%_50%_at_5%_90%,rgba(212,180,131,0.08),transparent_50%)]"
          aria-hidden
        />
        <div className="relative mx-auto grid max-w-[1120px] items-center gap-10 px-5 pb-12 pt-14 md:grid-cols-[1.05fr_0.95fr] md:gap-10 md:px-6 md:pb-16 md:pt-18 lg:pt-20">
          <div className="pb-2 md:pb-6">
            <p className="animate-rise inline-flex items-center gap-2 rounded-md border border-accent/30 bg-accent-soft/50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent studio-live-dot" />
              LinkedIn content operating system
            </p>
            <p className="display animate-rise mt-5 text-[2.75rem] leading-none text-ink sm:text-5xl md:text-6xl lg:text-[4.25rem]">
              Content<span className="text-accent">OS</span>
            </p>
            <HeroHeadline />
            <p className="animate-rise-delay-2 mt-5 max-w-md text-base leading-relaxed text-steel sm:text-lg">
              Train an AI agent on your brand. Generate posts. Approve every one before it goes live.
            </p>
            <span className="hero-glow-line animate-rise-delay-2" aria-hidden />
            <div className="animate-rise-delay-3 mt-7 flex flex-wrap items-center gap-3">
              <Link href="/contact" className="btn-primary btn-demo">
                Book a demo
              </Link>
              <Link href="/product" className="btn-secondary">
                See how it works
              </Link>
            </div>
            <p className="animate-rise-delay-3 mt-4 text-sm text-steel">
              Free 20-min walkthrough · No credit card · Human approval always on
            </p>
            <div className="animate-rise-delay-3 mt-5 flex flex-wrap gap-2">
              <span className="trust-chip">
                <span className="trust-chip-dot" />
                Human approval required
              </span>
              <span className="trust-chip">
                <span className="trust-chip-dot" />
                Teams · Agencies · Founders
              </span>
            </div>
          </div>

          <div className="animate-rise-delay-2 min-w-0 md:justify-self-end">
            <DraftStudio />
          </div>
        </div>
      </section>

      {/* Social proof strip */}
      <section className="border-y border-[var(--line)] bg-[rgba(20,40,32,0.6)]">
        <div className="section-inner px-5 py-7 md:px-6">
          <p className="text-center text-[11px] font-semibold uppercase tracking-[0.16em] text-steel">
            Built for teams who refuse generic LinkedIn AI
          </p>
          <div className="logo-marquee mt-5">
            <div className="logo-marquee-track">
              {[...logos, ...logos].map((name, i) => (
                <span key={`${name}-${i}`} className="logo-pill">
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Result metrics */}
      <section className="border-b border-[var(--line)]">
        <div className="section-inner grid gap-4 px-5 py-10 sm:grid-cols-2 md:grid-cols-4 md:px-6">
          {results.map((item) => (
            <CountUp key={item.label} value={item.value} label={item.label} />
          ))}
        </div>
      </section>

      {/* Outcomes */}
      <section className="border-b border-[var(--line)] bg-[rgba(11,18,16,0.35)]">
        <div className="section-inner grid gap-6 px-5 py-10 sm:grid-cols-2 md:grid-cols-4 md:px-6">
          {outcomes.map((item) => (
            <div key={item.title} className="hover-line border-l border-accent/40 pl-4">
              <p className="text-sm font-semibold text-ink">{item.title}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-steel">{item.copy}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Week cadence visual */}
      <section className="section">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow">The difference</p>
            <h2 className="display mt-3 max-w-3xl text-3xl text-ink md:text-[2.75rem]">
              Same week. Completely different LinkedIn.
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-steel">
              Stop rebuilding posts from scratch. ContentOS fills the calendar — you stay in control
              of every publish.
            </p>
          </Reveal>
          <Reveal>
            <div className="mt-10">
              <WeekCadence />
            </div>
          </Reveal>
        </div>
      </section>

      {/* Problem / Solution */}
      <section className="section section-band border-t border-[var(--line)]">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow">Why ContentOS</p>
            <h2 className="display mt-3 max-w-3xl text-3xl text-ink md:text-[2.75rem]">
              LinkedIn isn&apos;t hard. Showing up every week is.
            </h2>
          </Reveal>
          <div className="compare-grid mt-10">
            <Reveal>
              <div className="hover-lift h-full rounded-2xl border border-[var(--line)] bg-surface/60 p-7 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-wide text-steel">Today</p>
                <h3 className="mt-3 text-xl font-semibold text-ink">The bottleneck</h3>
                <ul className="mt-4 space-y-3 text-sm leading-relaxed text-steel">
                  <li className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-steel/60" />
                    Research, copy, and design stack up every week
                  </li>
                  <li className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-steel/60" />
                    Posts slip and brand voice drifts across writers
                  </li>
                  <li className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-steel/60" />
                    Teams burn hours on blank pages instead of shipping
                  </li>
                </ul>
              </div>
            </Reveal>
            <div className="compare-vs" aria-hidden>
              VS
            </div>
            <Reveal delay={100}>
              <div className="hover-lift h-full rounded-2xl border border-accent/40 bg-accent-soft/45 p-7 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                  With ContentOS
                </p>
                <h3 className="mt-3 text-xl font-semibold text-ink">The operating system</h3>
                <ul className="mt-4 space-y-3 text-sm leading-relaxed text-ink-soft">
                  <li className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    Train once on brand — drafts stay on-voice
                  </li>
                  <li className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    Generate captions and carousels in minutes
                  </li>
                  <li className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    Human approval before anything goes live
                  </li>
                </ul>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* Mid CTA */}
      <section className="section !pt-0">
        <div className="section-inner">
          <div className="mid-cta-band px-6 py-10 md:flex md:items-center md:justify-between md:px-10 md:py-12">
            <div>
              <p className="eyebrow">See it live</p>
              <h2 className="display mt-2 max-w-xl text-2xl text-ink md:text-3xl">
                Watch ContentOS draft your next LinkedIn post — then you approve.
              </h2>
              <p className="mt-3 max-w-lg text-sm text-steel">
                20-minute walkthrough. Bring your brand context. Leave with a clear fit.
              </p>
            </div>
            <Link href="/contact" className="btn-primary btn-demo mt-6 inline-flex md:mt-0">
              Book a 20-min demo
            </Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="section section-band">
        <div className="section-inner">
          <Reveal>
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="eyebrow">How it works</p>
                <h2 className="display mt-3 max-w-2xl text-3xl text-ink md:text-[2.75rem]">
                  Five steps from brand to LinkedIn.
                </h2>
              </div>
              <p className="max-w-sm text-sm leading-relaxed text-steel md:text-right">
                A repeatable loop — not a one-off prompt. Built for weekly shipping.
              </p>
            </div>
          </Reveal>

          <Reveal>
            <div className="mt-10">
              <PipelineVisual />
            </div>
          </Reveal>

          <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {steps.map((step, i) => (
              <Reveal key={step.title} delay={i * 60}>
                <li className="hover-step relative h-full">
                  <span className="hover-step-num display text-3xl text-accent/30">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-2 text-lg font-semibold text-ink">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-steel">{step.copy}</p>
                </li>
              </Reveal>
            ))}
          </ol>

          <Reveal>
            <div className="mt-10">
              <Link href="/product" className="btn-secondary">
                Walk through the product
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Platform */}
      <section className="section border-t border-[var(--line)]">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow">Platform</p>
            <h2 className="display mt-3 max-w-2xl text-3xl text-ink md:text-[2.75rem]">
              Everything you need to stop guessing and start shipping.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((item, i) => (
              <Reveal key={item.title} delay={(i % 3) * 70}>
                <div className="hover-lift glass-card h-full rounded-2xl border border-[var(--line)] p-6">
                  <span className="display text-2xl text-accent/35">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-3 text-lg font-semibold text-ink">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-steel">{item.copy}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal>
            <div className="mt-10">
              <Link href="/features" className="btn-secondary">
                Explore all features
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Audiences */}
      <section className="section section-band border-t border-[var(--line)]">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow">Who it&apos;s for</p>
            <h2 className="display mt-3 max-w-2xl text-3xl text-ink md:text-[2.75rem]">
              One platform. Three LinkedIn realities.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {audiences.map((item, i) => (
              <Reveal key={item.title} delay={i * 80}>
                <Link
                  href={item.href}
                  className="hover-lift flex h-full flex-col rounded-2xl border border-[var(--line)] bg-surface/70 p-6 transition"
                >
                  <h3 className="text-xl font-semibold text-ink">{item.title}</h3>
                  <p className="mt-4 flex-1 text-sm leading-relaxed text-ink-soft">{item.promise}</p>
                  <p className="mt-5 border-t border-[var(--line)] pt-4 text-xs leading-relaxed text-steel">
                    {item.proof}
                  </p>
                  <span className="mt-4 text-sm font-semibold text-accent">Learn more →</span>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Demo process */}
      <section className="section border-t border-[var(--line)]">
        <div className="section-inner">
          <Reveal>
            <p className="eyebrow">The demo</p>
            <h2 className="display mt-3 max-w-2xl text-3xl text-ink md:text-[2.75rem]">
              What you get in 20 minutes.
            </h2>
          </Reveal>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {demoSteps.map((step, i) => (
              <Reveal key={step.title} delay={i * 80}>
                <div className="hover-lift h-full rounded-2xl border border-[var(--line)] bg-surface/65 p-6">
                  <span className="display text-3xl text-accent/30">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-3 text-lg font-semibold text-ink">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-steel">{step.copy}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal>
            <div className="mt-10">
              <Link href="/contact" className="btn-primary btn-demo">
                Book your demo
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Trust */}
      <section className="section section-band border-t border-[var(--line)]">
        <div className="section-inner">
          <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
            <Reveal>
              <div>
                <p className="eyebrow">Trust by design</p>
                <h2 className="display mt-3 max-w-xl text-3xl text-ink md:text-[2.75rem]">
                  AI drafts. Humans decide. Brand stays yours.
                </h2>
                <p className="mt-4 max-w-xl text-lg leading-relaxed text-steel">
                  ContentOS is built for marketers who will not hand their company voice to
                  unsupervised automation. Approval is required — every time.
                </p>
                <div className="mt-8 flex flex-wrap gap-2">
                  <span className="trust-chip">
                    <span className="trust-chip-dot" />
                    Brand training
                  </span>
                  <span className="trust-chip">
                    <span className="trust-chip-dot" />
                    Approval required
                  </span>
                  <span className="trust-chip">
                    <span className="trust-chip-dot" />
                    Multi-tenant
                  </span>
                </div>
              </div>
            </Reveal>
            <div className="space-y-4">
              {quotes.map((item, i) => (
                <Reveal key={item.role} delay={i * 90}>
                  <blockquote className="hover-lift rounded-2xl border border-[var(--line)] bg-[#0a1511]/85 p-6">
                    <p className="quote-mark" aria-hidden>
                      &ldquo;
                    </p>
                    <p className="-mt-4 text-base leading-relaxed text-ink-soft">{item.quote}</p>
                    <footer className="mt-4 text-sm font-medium text-accent">{item.role}</footer>
                  </blockquote>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Objections / FAQ */}
      <section className="section border-t border-[var(--line)]">
        <div className="section-inner max-w-3xl">
          <Reveal>
            <p className="eyebrow">Common questions</p>
            <h2 className="display mt-3 text-3xl text-ink md:text-[2.5rem]">
              Built for skeptical marketers.
            </h2>
          </Reveal>
          <div className="mt-10">
            <FaqAccordion items={objections} />
          </div>
          <Reveal>
            <div className="mt-10">
              <Link href="/contact" className="btn-primary btn-demo">
                Still unsure? Book a demo
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Risk reversal */}
      <section className="section !pt-0">
        <div className="section-inner">
          <Reveal>
            <div className="guarantee-band">
              <div>
                <p className="text-sm font-semibold text-ink">No unsupervised posts</p>
                <p className="mt-1 text-xs leading-relaxed text-steel">
                  Every publish needs a human yes. Brand safety is built in.
                </p>
              </div>
              <div>
                <p className="text-sm font-semibold text-ink">Demo before commitment</p>
                <p className="mt-1 text-xs leading-relaxed text-steel">
                  See the loop with your brand context before you pick a plan.
                </p>
              </div>
              <div>
                <p className="text-sm font-semibold text-ink">Fit for your team</p>
                <p className="mt-1 text-xs leading-relaxed text-steel">
                  Sized for founders, in-house marketers, and multi-client agencies.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <MarketingCTA
        title="No more blank-page Mondays."
        description="See ContentOS generate on-brand LinkedIn drafts for your company — then decide if it belongs in your stack."
        primary={{ href: "/contact", label: "Book a demo" }}
        secondary={{ href: "/pricing", label: "View plans" }}
      />
    </>
  );
}
