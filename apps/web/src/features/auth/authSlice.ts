import { createSlice, type PayloadAction } from "@reduxjs/toolkit"

export type AuthUser = {
  userId: number
  username: string
  email: string
  roleName?: string
  tenantId?: number
  permissions?: string[]
  modulesEnabled?: string[]
}

type AuthState = {
  accessToken: string | null
  refreshToken: string | null
  user: AuthUser | null
}

const load = (): AuthState => {
  try {
    const raw = localStorage.getItem("contentos_auth")
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return { accessToken: null, refreshToken: null, user: null }
}

const initialState: AuthState = load()

const persist = (s: AuthState) => {
  localStorage.setItem("contentos_auth", JSON.stringify(s))
}

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setSession(
      state,
      action: PayloadAction<{
        accessToken: string
        refreshToken: string
        user: AuthUser
      }>,
    ) {
      state.accessToken = action.payload.accessToken
      state.refreshToken = action.payload.refreshToken
      state.user = action.payload.user
      persist(state)
    },
    setCredentials(
      state,
      action: PayloadAction<{ accessToken: string; refreshToken: string }>,
    ) {
      state.accessToken = action.payload.accessToken
      state.refreshToken = action.payload.refreshToken
      persist(state)
    },
    logout(state) {
      state.accessToken = null
      state.refreshToken = null
      state.user = null
      localStorage.removeItem("contentos_auth")
    },
  },
})

export const { setSession, setCredentials, logout } = authSlice.actions
export default authSlice.reducer
