import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { Provider } from "react-redux"
import { BrowserRouter } from "react-router-dom"
import { registerSW } from "virtual:pwa-register"
import { store } from "@/app/store"
import { AppRouter } from "@/app/router"
import "./index.css"

registerSW({ immediate: true })

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "") || "/"}>
        <AppRouter />
      </BrowserRouter>
    </Provider>
  </StrictMode>,
)
