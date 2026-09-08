# ContentOS marketing site

Public marketing site for ContentOS — a B2B LinkedIn content operating system.

Static pages are served at CloudFront **`/`**. The product SPA is served at **`/app/`**.

CDK deploys the Next.js static export from `out/` (`output: "export"`).

## Getting started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Production build

```bash
npm run build
```

Writes static files to `out/` for S3 / CloudFront.

## Pages

- `/` — Home
- `/product` — How it works
- `/features` — Capabilities
- `/use-cases` — Audience solutions
- `/pricing` — Plans
- `/about` — Company
- `/contact` — Request a demo
