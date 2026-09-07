import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Suspense } from "react";
import { Syne, IBM_Plex_Sans } from "next/font/google";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { ScrollProgress } from "@/components/ScrollProgress";
import { StickyDemoCTA } from "@/components/StickyDemoCTA";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  weight: ["500", "600", "700", "800"],
});

const ibmPlex = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-ibm",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "ContentOS — LinkedIn content on autopilot",
    template: "%s · ContentOS",
  },
  description:
    "Train an AI agent on your brand, generate on-brand LinkedIn posts, and approve every post before it goes live. Built for marketing teams, agencies, and founders.",
  keywords: [
    "LinkedIn content",
    "AI LinkedIn posts",
    "brand voice AI",
    "content operating system",
    "marketing automation",
    "agency LinkedIn",
    "founder LinkedIn",
    "LinkedIn content generator",
  ],
  openGraph: {
    title: "ContentOS — LinkedIn content on autopilot",
    description:
      "Train it once. Publish on-brand LinkedIn content every week — with human review before every post.",
    type: "website",
    siteName: "ContentOS",
  },
  twitter: {
    card: "summary_large_image",
    title: "ContentOS — LinkedIn content on autopilot",
    description:
      "Train once. Generate on-brand drafts. Approve before publish. Built for teams, agencies & founders.",
  },
  icons: {
    icon: [{ url: "/favicon.png", type: "image/png" }],
    apple: [{ url: "/favicon.png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en" className={`${syne.variable} ${ibmPlex.variable}`}>
      <body className="antialiased">
        <div className="site-bg min-h-screen">
          <ScrollProgress />
          <Suspense fallback={<header className="h-[64px] border-b border-[var(--line)]" />}>
            <Header />
          </Suspense>
          <main>{children}</main>
          <Footer />
          <Suspense fallback={null}>
            <StickyDemoCTA />
          </Suspense>
        </div>
      </body>
    </html>
  );
}
