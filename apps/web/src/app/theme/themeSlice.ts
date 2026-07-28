import { createSlice, type PayloadAction } from "@reduxjs/toolkit"
import type { ThemePayload } from "@/features/api/contentApi"

type ThemeState = {
  colorMode: "light" | "dark"
  brand: ThemePayload | null
}

const savedMode = (localStorage.getItem("contentos_color_mode") as "light" | "dark") || "light"

const initialState: ThemeState = {
  colorMode: savedMode,
  brand: null,
}

const themeSlice = createSlice({
  name: "theme",
  initialState,
  reducers: {
    setColorMode(state, action: PayloadAction<"light" | "dark">) {
      state.colorMode = action.payload
      localStorage.setItem("contentos_color_mode", action.payload)
      document.documentElement.classList.toggle("dark", action.payload === "dark")
    },
    setBrand(state, action: PayloadAction<ThemePayload>) {
      state.brand = action.payload
      applyBrandCss(action.payload)
    },
  },
})

export function applyBrandCss(brand: ThemePayload) {
  const root = document.documentElement
  if (brand.source === "tenant" && brand.uiMode === "white_label") {
    root.style.setProperty("--primary", brand.colors.primary)
    root.style.setProperty("--secondary", brand.colors.secondary)
    root.style.setProperty("--accent", brand.colors.accent)
    root.style.setProperty("--ring", brand.colors.primary)
  } else {
    root.style.removeProperty("--primary")
    root.style.removeProperty("--secondary")
    root.style.removeProperty("--accent")
    root.style.removeProperty("--ring")
  }
}

export const { setColorMode, setBrand } = themeSlice.actions
export default themeSlice.reducer
