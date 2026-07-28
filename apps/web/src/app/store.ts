import { configureStore } from "@reduxjs/toolkit"
import authReducer from "@/features/auth/authSlice"
import { authApi } from "@/features/auth/authApi"
import { contentApi } from "@/features/api/contentApi"
import themeReducer from "@/app/theme/themeSlice"

export const store = configureStore({
  reducer: {
    auth: authReducer,
    theme: themeReducer,
    [authApi.reducerPath]: authApi.reducer,
    [contentApi.reducerPath]: contentApi.reducer,
  },
  middleware: (getDefault) =>
    getDefault().concat(authApi.middleware, contentApi.middleware),
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
