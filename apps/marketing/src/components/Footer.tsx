import Link from "next/link";

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
      { href: "/contact", label: "Book a demo" },
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
        className="pointer-events-none absolute -top-24 left-1/2 h-48 w-[28rem] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl"
        aria-hidden
      />
      <div className="section-inner relative px-5 py-16 md:px-6">
        <div className="mid-cta-band mb-12 px-6 py-8 md:flex md:items-center md:justify-between md:px-8">
          <div>
            <p className="display text-2xl text-ink md:text-3xl">Ready to ship on-brand?</p>
            <p className="mt-2 max-w-md text-sm text-steel">
              Book a demo and see ContentOS train, generate, review, and publish in one loop.
            </p>
          </div>
          <Link href="/contact" className="btn-primary btn-demo mt-5 inline-flex md:mt-0">
            Book a demo
          </Link>
        </div>

        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Link href="/" className="display text-2xl text-ink">
              Content<span className="text-accent">OS</span>
            </Link>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-steel">
              LinkedIn content on autopilot — without losing your voice. Built by TechPotato Softwares
              LLP.
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
            <form className="mt-6 flex max-w-sm gap-2" action="/contact">
              <label htmlFor="newsletter" className="sr-only">
                Email for updates
              </label>
              <input
                id="newsletter"
                name="email"
                type="email"
                placeholder="Work email"
                className="field-input min-w-0 flex-1 !py-2.5"
              />
              <button type="submit" className="btn-primary !px-3 !py-2.5 !text-sm">
                Subscribe
              </button>
            </form>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <p className="text-sm font-semibold text-ink">{col.title}</p>
              <ul className="mt-3 space-y-2">
                {col.links.map((link) => (
                  <li key={`${col.title}-${link.label}`}>
                    <Link href={link.href} className="text-sm text-steel transition hover:text-ink">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-2 border-t border-[var(--line)] pt-6 text-sm text-steel md:flex-row md:items-center md:justify-between">
          <p>© {new Date().getFullYear()} TechPotato Softwares LLP. All rights reserved.</p>
          <p>LinkedIn content operating system for teams.</p>
        </div>
      </div>
    </footer>
  );
}
