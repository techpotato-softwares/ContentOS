import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { VitePWA } from "vite-plugin-pwa"

const apiProxy = {
  "/api": "http://localhost:4001",
  "/health": "http://localhost:4001",
  "/media": "http://localhost:4001",
}

/**
 * Chrome/Edge Android show ⋮ → “Install app” only when installability criteria pass:
 * HTTPS (or localhost), valid manifest, SW with fetch handler, 192+512 PNG icons.
 */
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: null, // we register explicitly in main.tsx
      includeAssets: [
        "favicon.svg",
        "icons.svg",
        "apple-touch-icon.png",
        "pwa-192.png",
        "pwa-512.png",
        "pwa-512-maskable.png",
      ],
      manifest: {
        id: "./",
        name: "ContentOS",
        short_name: "ContentOS",
        description: "B2B LinkedIn image content operating system",
        lang: "en",
        dir: "ltr",
        start_url: "./",
        scope: "./",
        display: "standalone",
        // Installed icon → app window; same URL in Chrome tab → normal website
        display_override: ["standalone", "minimal-ui", "browser"],
        orientation: "any",
        theme_color: "#0d9488",
        background_color: "#f4f7f6",
        prefer_related_applications: false,
        categories: ["business", "productivity"],
        icons: [
          {
            src: "pwa-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "pwa-512-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2,webmanifest}"],
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api/, /^\/health/, /^\/media/],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        runtimeCaching: [
          {
            urlPattern: ({ url }) =>
              url.origin === "https://fonts.googleapis.com" ||
              url.origin === "https://fonts.gstatic.com",
            handler: "CacheFirst",
            options: {
              cacheName: "google-fonts",
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      // Dev SW often 500s if sw.js isn't generated yet and blocks the UI with Vite overlay.
      // Enable only when intentionally testing installability locally.
      devOptions: {
        enabled: false,
        type: "module",
        navigateFallback: "index.html",
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: {
    port: 4173,
    proxy: apiProxy,
  },
})
