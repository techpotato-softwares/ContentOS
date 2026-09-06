import Link from "next/link";

export default function NotFound() {
  return (
    <section className="section">
      <div className="section-inner py-20 text-center">
        <p className="eyebrow">404</p>
        <h1 className="display mt-3 text-4xl text-ink md:text-5xl">Page not found</h1>
        <p className="mx-auto mt-4 max-w-md text-steel">
          That route doesn&apos;t exist. Head back home and keep shipping LinkedIn content.
        </p>
        <Link href="/" className="btn-primary mt-8 inline-flex">
          Back to home
        </Link>
      </div>
    </section>
  );
}
