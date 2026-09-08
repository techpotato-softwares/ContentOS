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

export default defineConfig({
  // Deployed: VITE_BASE=/app/  |  Local default: /
  base: process.env.VITE_BASE || "/",
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "icons.svg", "apple-touch-icon.png"],
      manifest: {
        name: "ContentOS",
        short_name: "ContentOS",
        description: "B2B LinkedIn image content operating system",
        theme_color: "#0d9488",
        background_color: "#f4f7f6",
        display: "standalone",
        orientation: "portrait-primary",
        categories: ["business", "productivity"],
        icons: [
          { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "pwa-512.png",
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
            },
          },
        ],
      },
      devOptions: { enabled: true },
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
