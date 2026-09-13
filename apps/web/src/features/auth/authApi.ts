import { createApi } from "@reduxjs/toolkit/query/react"
import { baseQueryWithReauth, unwrapData } from "@/shared/lib/apiBase"
import type { AuthUser } from "./authSlice"

type LoginResponse = {
  accessToken: string
  refreshToken: string
  user: AuthUser
  message?: string
}

type RequestOtpResponse = {
  success: boolean
  message: string
  email: string
  expiresIn: number
  otpId?: number
  inboxUrl?: string
}

/** Absolute API origin for full-page OAuth redirects (not relative SPA paths). */
export function apiOrigin(): string {
  const raw = (import.meta.env.VITE_API_URL as string | undefined) || ""
  if (raw) return raw.replace(/\/$/, "")
  // Dev: leave empty so browser hits Vite proxy (/api → :4001)
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
    requestOtp: build.mutation<RequestOtpResponse, { email: string }>({
      query: (body) => ({
        url: "/api/auth/otp/request",
        method: "POST",
        body: { email: body.email.trim().toLowerCase() },
      }),
      transformResponse: (r: unknown) => unwrapData<RequestOtpResponse>(r),
    }),
    verifyOtp: build.mutation<LoginResponse, { email: string; code: string }>({
      query: (body) => ({
        url: "/api/auth/otp/verify",
        method: "POST",
        body: {
          email: body.email.trim().toLowerCase(),
          code: body.code.trim(),
        },
      }),
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
      {
        username: string
        email: string
        password: string
        companyName?: string
        inviteToken?: string
      }
    >({
      query: (body) => ({
        url: "/api/register",
        method: "POST",
        body: {
          username: body.username,
          email: body.email,
          password: body.password,
          companyName: body.companyName,
          inviteToken: body.inviteToken,
        },
      }),
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    requestEmailVerification: build.mutation<
      { success?: boolean; message: string; link?: string },
      { email: string }
    >({
      query: (body) => ({
        url: "/api/auth/verify-email/request",
        method: "POST",
        body: { email: body.email },
      }),
      transformResponse: (r: unknown) =>
        unwrapData<{ success?: boolean; message: string; link?: string }>(r),
    }),
    confirmEmailVerification: build.mutation<LoginResponse, { token: string }>({
      query: (body) => ({
        url: "/api/auth/verify-email/confirm",
        method: "POST",
        body: { token: body.token },
      }),
      transformResponse: (r: unknown) => unwrapData<LoginResponse>(r),
    }),
    requestPasswordReset: build.mutation<
      { success?: boolean; message: string; link?: string },
      { email: string }
    >({
      query: (body) => ({
        url: "/api/auth/password-reset/request",
        method: "POST",
        body: { email: body.email },
      }),
      transformResponse: (r: unknown) =>
        unwrapData<{ success?: boolean; message: string; link?: string }>(r),
    }),
    confirmPasswordReset: build.mutation<
      { success?: boolean; message: string },
      { token: string; password: string }
    >({
      query: (body) => ({
        url: "/api/auth/password-reset/confirm",
        method: "POST",
        body: { token: body.token, password: body.password },
      }),
      transformResponse: (r: unknown) => unwrapData<{ success?: boolean; message: string }>(r),
    }),
  }),
})

export const {
  useLoginMutation,
  useRegisterMutation,
  useRequestOtpMutation,
  useVerifyOtpMutation,
  useExchangeGoogleCodeMutation,
  useRequestEmailVerificationMutation,
  useConfirmEmailVerificationMutation,
  useRequestPasswordResetMutation,
  useConfirmPasswordResetMutation,
} = authApi
