import type { Metadata } from "next";
import { PageHero } from "@/components/PageHero";
import { ContactForm } from "@/components/ContactForm";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Request a demo",
  description: "Request a ContentOS demo for your marketing team, agency, or personal brand.",
};

export default function ContactPage() {
  return (
    <>
      <PageHero
        eyebrow="Contact"
        title="Book a demo — see ContentOS with your brand in mind."
        description="Tell us about your team and LinkedIn goals. We'll walk train → generate → review → publish in one focused session."
      />

      <section className="section">
        <div className="section-inner grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-14">
          <Reveal>
            <ContactForm />
          </Reveal>

          <Reveal delay={100}>
            <aside className="space-y-5">
              <div className="glass-card rounded-2xl border border-[var(--line)] p-6">
                <h2 className="text-lg font-semibold text-ink">What happens next</h2>
                <ol className="mt-4 space-y-4">
                  {[
                    "We confirm brands, seats, and LinkedIn cadence.",
                    "Live walkthrough of train → generate → review → publish.",
                    "Optional pilot plan tailored to your team.",
                  ].map((step, i) => (
                    <li key={step} className="flex gap-3 text-sm leading-relaxed text-steel">
                      <span className="display flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent/15 text-sm text-accent">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>

              <div className="glass-card rounded-2xl border border-accent/25 bg-accent-soft/25 p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                  Average demo
                </p>
                <p className="display mt-2 text-3xl text-ink">20 min</p>
                <p className="mt-2 text-sm text-steel">
                  No pitch deck marathon — just the loop with your brand context.
                </p>
              </div>

              <div className="glass-card rounded-2xl border border-[var(--line)] p-6">
                <h2 className="text-lg font-semibold text-ink">Direct contact</h2>
                <p className="mt-2 text-steel">TechPotato Softwares LLP</p>
                <a
                  href="mailto:hello@contentos.app"
                  className="mt-3 inline-block font-medium text-accent transition hover:underline"
                >
                  hello@contentos.app
                </a>
              </div>

              <div className="glass-card rounded-2xl border border-[var(--line)] p-6">
                <h2 className="text-lg font-semibold text-ink">Who this demo is for</h2>
                <ul className="mt-3 space-y-2 text-sm text-steel">
                  <li className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    In-house marketing teams
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    Agencies managing multiple clients
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    Founders building a personal brand
                  </li>
                </ul>
              </div>
            </aside>
          </Reveal>
        </div>
      </section>
    </>
  );
}
