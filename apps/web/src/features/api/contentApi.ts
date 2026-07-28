import { createApi } from "@reduxjs/toolkit/query/react"
import { baseQueryWithReauth, unwrapData } from "@/shared/lib/apiBase"
import type { TenantTrainingSchema } from "@/shared/types/training"

export type ThemePayload = {
  source: "platform" | "tenant"
  uiMode: "platform" | "white_label"
  appDisplayName: string
  logoUrl: string | null
  colors: { primary: string; secondary: string; accent: string }
}

export type TenantRow = {
  tenantId: number
  name: string
  slug: string
  uiMode: string
  appDisplayName?: string
  logoUrl?: string
  primaryColor?: string
  secondaryColor?: string
  accentColor?: string
}

export type ContentPost = {
  postId: number
  batchId?: number
  angle: string
  caption: string
  imageUrl?: string
  status: string
  linkedinPostId?: string
}

export type ChatSessionRow = {
  sessionId: number
  title: string
  updatedAt?: string | null
}

export type ChatMessageRow = {
  messageId: number
  role: string
  content: string
  createdAt?: string | null
}

export type ContentSuggestion = {
  title: string
  angle: string
  brief: string
  why: string
}

export type IndustryNewsItem = {
  headline: string
  summary: string
  suggestedBrief: string
  sourceNote: string
}

export type AnalyticsInsights = {
  summary: string
  bestTimes: string[]
  suggestedTopics: string[]
  recommendations: string[]
  metrics?: Record<string, string | number>
  placeholder?: boolean
}

export const contentApi = createApi({
  reducerPath: "contentApi",
  baseQuery: baseQueryWithReauth,
  tagTypes: ["Theme", "Training", "Tenants", "Posts", "LinkedIn", "Batch", "Sessions", "Insights"],
  endpoints: (build) => ({
    getTheme: build.query<ThemePayload, void>({
      query: () => "/api/tenants/me/theme",
      transformResponse: (r: unknown) => unwrapData<ThemePayload>(r),
      providesTags: ["Theme"],
    }),
    listTenants: build.query<TenantRow[], void>({
      query: () => "/api/admin/tenants",
      transformResponse: (r: unknown) => unwrapData<TenantRow[]>(r),
      providesTags: ["Tenants"],
    }),
    createTenant: build.mutation<TenantRow, { name: string; slug?: string }>({
      query: (body) => ({ url: "/api/admin/tenants", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData<TenantRow>(r),
      invalidatesTags: ["Tenants"],
    }),
    getTraining: build.query<TenantTrainingSchema, number | void>({
      query: (tenantId) =>
        tenantId
          ? `/api/admin/tenants/${tenantId}/training`
          : "/api/tenants/me/training",
      transformResponse: (r: unknown) => unwrapData<TenantTrainingSchema>(r),
      providesTags: ["Training"],
    }),
    putTraining: build.mutation<
      unknown,
      { tenantId?: number; body: TenantTrainingSchema }
    >({
      query: ({ tenantId, body }) => ({
        url: tenantId
          ? `/api/admin/tenants/${tenantId}/training`
          : "/api/tenants/me/training",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Training", "Theme"],
    }),
    previewTraining: build.query<
      { training: TenantTrainingSchema; contextPack: string; version: number },
      number
    >({
      query: (tenantId) => `/api/admin/tenants/${tenantId}/training/preview`,
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    listSessions: build.query<ChatSessionRow[], void>({
      query: () => "/api/agent/sessions",
      transformResponse: (r: unknown) => unwrapData<ChatSessionRow[]>(r),
      providesTags: ["Sessions"],
    }),
    getSessionMessages: build.query<
      { sessionId: number; title: string; messages: ChatMessageRow[] },
      number
    >({
      query: (sessionId) => `/api/agent/sessions/${sessionId}/messages`,
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    chat: build.mutation<
      { sessionId: number; reply: string },
      { message: string; sessionId?: number }
    >({
      query: (body) => ({ url: "/api/agent/chat", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Sessions"],
    }),
    generate: build.mutation<
      { batchId: number; posts: ContentPost[] },
      { brief: string; sessionId?: number; newsContext?: string }
    >({
      query: (body) => ({ url: "/api/agent/generate", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts", "Sessions"],
    }),
    getSuggestions: build.query<{ suggestions: ContentSuggestion[] }, void>({
      query: () => "/api/agent/insights/suggestions",
      transformResponse: (r: unknown) => unwrapData(r),
      providesTags: ["Insights"],
    }),
    getIndustryNews: build.query<
      { industry: string; items: IndustryNewsItem[]; mode: string },
      void
    >({
      query: () => "/api/agent/insights/news",
      transformResponse: (r: unknown) => unwrapData(r),
      providesTags: ["Insights"],
    }),
    getAnalyticsInsights: build.query<AnalyticsInsights, void>({
      query: () => "/api/agent/insights/analytics",
      transformResponse: (r: unknown) => unwrapData(r),
      providesTags: ["Insights"],
    }),
    listPosts: build.query<ContentPost[], string | void>({
      query: (status) => (status ? `/api/posts?status=${status}` : "/api/posts"),
      transformResponse: (r: unknown) => unwrapData<ContentPost[]>(r),
      providesTags: ["Posts"],
    }),
    submitReview: build.mutation<ContentPost, number>({
      query: (id) => ({ url: `/api/posts/${id}/submit-review`, method: "POST" }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    approvePost: build.mutation<ContentPost, number>({
      query: (id) => ({ url: `/api/posts/${id}/approve`, method: "POST" }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    rejectPost: build.mutation<ContentPost, number>({
      query: (id) => ({ url: `/api/posts/${id}/reject`, method: "POST", body: {} }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    publishPost: build.mutation<ContentPost, number>({
      query: (id) => ({ url: `/api/posts/${id}/publish`, method: "POST" }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    linkedInStatus: build.query<{ connected: boolean; username?: string }, void>({
      query: () => "/api/social/linkedin/status",
      transformResponse: (r: unknown) => unwrapData(r),
      providesTags: ["LinkedIn"],
    }),
    linkedInConnect: build.mutation<{ authorizeUrl: string }, void>({
      query: () => ({ url: "/api/social/linkedin/connect", method: "GET" }),
      transformResponse: (r: unknown) => unwrapData(r),
    }),
  }),
})

export const {
  useGetThemeQuery,
  useListTenantsQuery,
  useCreateTenantMutation,
  useGetTrainingQuery,
  usePutTrainingMutation,
  useLazyPreviewTrainingQuery,
  useListSessionsQuery,
  useLazyGetSessionMessagesQuery,
  useChatMutation,
  useGenerateMutation,
  useGetSuggestionsQuery,
  useGetIndustryNewsQuery,
  useGetAnalyticsInsightsQuery,
  useListPostsQuery,
  useSubmitReviewMutation,
  useApprovePostMutation,
  useRejectPostMutation,
  usePublishPostMutation,
  useLinkedInStatusQuery,
  useLinkedInConnectMutation,
} = contentApi
