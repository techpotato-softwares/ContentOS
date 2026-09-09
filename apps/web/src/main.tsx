import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { Provider } from "react-redux"
import { BrowserRouter } from "react-router-dom"
import { registerSW } from "virtual:pwa-register"
import { store } from "@/app/store"
import { AppRouter } from "@/app/router"
import "./index.css"

// Explicit SW registration so Chrome can mark the site installable
// (⋮ menu → Install app on Android Chrome, like linkplease.co).
registerSW({
  immediate: true,
  onRegisteredSW(_url, registration) {
    if (!registration) return
    setInterval(() => {
      void registration.update()
    }, 60 * 60 * 1000)
  },
  onRegisterError(error) {
    console.warn("[PWA] Service worker registration failed:", error)
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "") || "/"}>
        <AppRouter />
      </BrowserRouter>
    </Provider>
  </StrictMode>,
)
