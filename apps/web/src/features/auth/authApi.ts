import { createApi } from "@reduxjs/toolkit/query/react"
import { baseQueryWithReauth, unwrapData } from "@/shared/lib/apiBase"
import type { AuthUser } from "./authSlice"

type LoginResponse = {
  accessToken: string
  refreshToken: string
  user: AuthUser
  message?: string
}

/** Absolute API origin for full-page OAuth redirects (not relative SPA paths). */
export function apiOrigin(): string {
  const raw = (import.meta.env.VITE_API_URL as string | undefined) || ""
  if (raw) return raw.replace(/\/$/, "")
  if (typeof window !== "undefined") return window.location.origin
  return ""
}

export function googleOAuthStartUrl(): string {
  return `${apiOrigin()}/api/auth/google/start`
}

export const authApi = createApi({
  reducerPath: "authApi",
  baseQuery: baseQueryWithReauth,
  endpoints: (build) => ({
    login: build.mutation<LoginResponse, { username: string; password: string }>({
      query: (body) => ({ url: "/api/login", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData<LoginResponse>(r),
    }),
    exchangeGoogleCode: build.mutation<LoginResponse, { code: string }>({
      query: (body) => ({
        url: "/api/auth/google/exchange",
        method: "POST",
        body: { code: body.code },
      }),
      transformResponse: (r: unknown) => unwrapData<LoginResponse>(r),
    }),
    register: build.mutation<
      LoginResponse & { tenant?: { tenantId: number; name: string; slug?: string } },
      { username: string; email: string; password: string; companyName: string }
    >({
      query: (body) => ({
        url: "/api/register",
        method: "POST",
        body: {
          username: body.username,
          email: body.email,
          password: body.password,
          companyName: body.companyName,
        },
      }),
      transformResponse: (r: unknown) => unwrapData(r),
    }),
  }),
})

export const {
  useLoginMutation,
  useRegisterMutation,
  useExchangeGoogleCodeMutation,
} = authApi
