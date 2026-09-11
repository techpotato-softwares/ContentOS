import type { Metadata } from "next";
import Link from "next/link";
import { appLoginUrl } from "@/lib/appUrl";
import { PageHero } from "@/components/PageHero";
import { MarketingCTA } from "@/components/MarketingCTA";
import { MarketingImage } from "@/components/MarketingImage";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Use cases",
  description:
    "ContentOS for in-house marketing teams, agencies managing many clients, and founders building personal brands.",
};

const cases = [
  {
    id: "teams",
    title: "In-house marketing teams",
    pain: "LinkedIn takes too much time. Design and copy bottleneck. Inconsistent posting.",
    want: "Post consistently on-brand, in minutes, without a designer.",
    points: [
      "Shared brand training across the team",
      "Review queue for managers and editors",
      "Insights that keep the calendar full",
    ],
    image: "/images/usecase-teams.webp",
    imageAlt: "Marketing team reviewing LinkedIn drafts in ContentOS",
  },
  {
    id: "agencies",
    title: "Marketing & social agencies",
    pain: "Managing content for many clients is manual and hard to scale.",
    want: "Run every client's LinkedIn from one multi-tenant workspace.",
    points: [
      "Separate workspaces per client brand",
      "Role-based access for account teams",
      "Faster turnaround without sacrificing voice",
    ],
    image: "/images/usecase-agency.webp",
    imageAlt: "Agency desk running multiple ContentOS brand workspaces",
  },
  {
    id: "founders",
    title: "Founders & personal brand builders",
    pain: "No time or skill to write and design LinkedIn posts regularly.",
    want: "Train the AI on your voice once — it writes and designs for you.",
    points: [
      "Voice-trained drafts that still sound like you",
      "Approve before anything publishes",
      "Carousels and captions without a design stack",
    ],
    image: "/images/usecase-founder.webp",
    imageAlt: "Founder workspace drafting a personal brand LinkedIn post",
  },
];

export default function UseCasesPage() {
  return (
    <>
      <PageHero
        eyebrow="Use cases"
        title="Same platform. Different LinkedIn realities."
        description="Whether you own one brand or fifty, ContentOS keeps voice consistent and publishing sustainable."
        primaryCta={{ href: appLoginUrl(), label: "Start Free" }}
        secondaryCta={{ href: "/pricing", label: "View plans" }}
      />

      <section className="section">
        <div className="section-inner space-y-8">
          {cases.map((item, index) => (
            <Reveal key={item.id} delay={index * 80}>
              <article
                id={item.id}
                className="hover-lift scroll-mt-28 overflow-hidden rounded-2xl border border-[var(--line)] bg-surface/70"
              >
                <div
                  className={`grid md:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] ${
                    index % 2 === 1
                      ? "md:[&>*:first-child]:order-2 md:[&>*:last-child]:order-1"
                      : ""
                  }`}
                >
                  <MarketingImage
                    src={item.image}
                    alt={item.imageAlt}
                    variant="panel"
                    badge={`0${index + 1}`}
                    eyebrow={item.title}
                    caption={item.want}
                    className="aspect-[16/11] w-full md:aspect-auto md:min-h-[320px] md:h-full"
                    sizes="(max-width: 768px) 100vw, 45vw"
                  />
                  <div
                    className={`border-t border-[var(--line)] md:border-t-0 ${
                      index % 2 === 1
                        ? "md:border-r md:border-[var(--line)]"
                        : "md:border-l md:border-[var(--line)]"
                    }`}
                  >
                    <div className="border-b border-[var(--line)] bg-[#0b1210]/40 px-6 py-5 md:px-8">
                      <span className="display text-accent/40">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <h2 className="display mt-2 text-2xl text-ink md:text-3xl">{item.title}</h2>
                    </div>
                    <div className="grid gap-0 sm:grid-cols-2">
                      <div className="border-b border-[var(--line)] p-6 sm:border-b-0 sm:border-r sm:p-8">
                        <p className="text-xs font-semibold uppercase tracking-wide text-steel">
                          Pain point today
                        </p>
                        <p className="mt-3 text-base leading-relaxed text-ink-soft md:text-lg">
                          {item.pain}
                        </p>
                      </div>
                      <div className="p-6 sm:p-8">
                        <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                          What they want to hear
                        </p>
                        <p className="mt-3 text-base leading-relaxed text-ink md:text-lg">
                          {item.want}
                        </p>
                      </div>
                    </div>
                    <div className="border-t border-[var(--line)] px-6 py-5 md:flex md:items-center md:justify-between md:px-8">
                      <ul className="grid flex-1 gap-3 sm:grid-cols-3">
                        {item.points.map((point) => (
                          <li key={point} className="flex gap-2 text-sm text-steel">
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                      <Link
                        href={appLoginUrl()}
                        className="btn-primary btn-demo mt-5 inline-flex shrink-0 !px-4 !py-2.5 !text-sm md:mt-0 md:ml-6"
                      >
                        Start Free
                      </Link>
                    </div>
                  </div>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
        <div className="section-inner mt-12">
          <Link href="/features" className="btn-secondary">
            Explore features
          </Link>
        </div>
      </section>

      <MarketingCTA
        title="Your LinkedIn reality, covered."
        description="Whether you own one brand or fifty — ContentOS keeps voice consistent and publishing sustainable."
      />
    </>
  );
}
