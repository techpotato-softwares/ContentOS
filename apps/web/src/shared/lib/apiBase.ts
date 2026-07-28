import {
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react"
import type { RootState } from "@/app/store"
import { setCredentials, logout } from "@/features/auth/authSlice"

const rawBaseQuery = fetchBaseQuery({
  baseUrl: import.meta.env.VITE_API_URL || "",
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.accessToken
    if (token) headers.set("Authorization", `Bearer ${token}`)
    headers.set("Content-Type", "application/json")
    return headers
  },
})

export const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extra) => {
  let result = await rawBaseQuery(args, api, extra)
  if (result.error && result.error.status === 401) {
    const refresh = (api.getState() as RootState).auth.refreshToken
    if (refresh) {
      const refreshResult = await rawBaseQuery(
        {
          url: "/api/auth/refresh",
          method: "POST",
          body: { refreshToken: refresh },
        },
        api,
        extra,
      )
      const data = (refreshResult.data as { data?: { accessToken?: string; refreshToken?: string } })
        ?.data
      if (data?.accessToken) {
        api.dispatch(
          setCredentials({
            accessToken: data.accessToken,
            refreshToken: data.refreshToken || refresh,
          }),
        )
        result = await rawBaseQuery(args, api, extra)
      } else {
        api.dispatch(logout())
      }
    } else {
      api.dispatch(logout())
    }
  }
  return result
}

/** Unwrap ContentOS envelope { success, data } */
export function unwrapData<T>(response: unknown): T {
  const r = response as { data?: T; success?: boolean }
  return (r?.data ?? response) as T
}
