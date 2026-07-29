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
  headline?: string
  subhead?: string
  bullets?: string[]
  layout?: {
    headline?: string
    subhead?: string
    bullets?: string[]
    caption?: string
  }
  score?: PostScore
  sourceType?: string
  sourceRef?: string
  abLabel?: string
  scheduledAt?: string | null
  publishedAt?: string | null
}

export type PostScore = {
  clarity: number
  hook: number
  brandFit: number
  cta: number
  overall: number
  summary: string
  fixes: string[]
}

export type AbScheduleSuggestion = {
  label: string
  postId: number
  angle?: string
  scheduledAt: string
  slotHint?: string
  reason?: string
}

export type AbScheduleResult = {
  batchId: number
  strategy: string
  suggestions: AbScheduleSuggestion[]
  applied: boolean
  posts: ContentPost[]
}

export type RepurposeResult = {
  batchId?: number
  posts: ContentPost[]
  extracted: {
    sourceType: string
    sourceRef: string
    title: string
    text: string
    charCount: number
    brief: string
  }
  preset?: string
  renderMode?: string
}

export type WeeklySnapshot = {
  tenantId?: number
  tenantName?: string
  stats: {
    generated: number
    batches: number
    draft: number
    pendingReview: number
    approved: number
    published: number
    scheduledUpcoming: number
    byAngle: Record<string, number>
    topPost?: {
      postId: number
      angle: string
      status: string
      headline?: string
      captionPreview?: string
    } | null
    auditEvents: number
    periodStart: string
    periodEnd: string
  }
  tenants?: unknown[]
}

export type ImageModelInfo = {
  id: string
  label: string
  provider: string
  nativeTextQuality: string
  bestFor: string
  supportedSizes: string[]
  costHint: string
  available: boolean
}

export type ImageModelsPayload = {
  models: ImageModelInfo[]
  presets: { id: string; width: number; height: number }[]
  defaultPreset: string
  defaultRenderMode: string
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
    uploadLogo: build.mutation<
      { logoUrl: string; training?: TenantTrainingSchema },
      { imageBase64: string; contentType: string; filename?: string; tenantId?: number }
    >({
      query: ({ tenantId, ...body }) => ({
        url: tenantId
          ? `/api/admin/tenants/${tenantId}/brand/logo`
          : "/api/tenants/me/brand/logo",
        method: "POST",
        body: tenantId ? { ...body, tenantId } : body,
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Training", "Theme"],
    }),
    deleteLogo: build.mutation<{ deleted: boolean }, number | void>({
      query: (tenantId) => ({
        url: tenantId
          ? `/api/tenants/me/brand/logo?tenantId=${tenantId}`
          : "/api/tenants/me/brand/logo",
        method: "DELETE",
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Training", "Theme"],
    }),
    getImageModels: build.query<ImageModelsPayload, void>({
      query: () => "/api/agent/image-models",
      transformResponse: (r: unknown) => unwrapData(r),
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
      {
        sessionId: number
        title: string
        messages: ChatMessageRow[]
        batchId?: number | null
        posts?: ContentPost[]
      },
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
      {
        batchId: number
        sessionId?: number
        posts: ContentPost[]
        preset?: string
        renderMode?: string
        imageModel?: string
        sourceType?: string
      },
      {
        brief: string
        sessionId?: number
        newsContext?: string
        preset?: string
        renderMode?: string
        imageModel?: string
        sourceType?: string
        sourceRef?: string
        userNote?: string
      }
    >({
      query: (body) => ({ url: "/api/agent/generate", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts", "Sessions"],
    }),
    scorePost: build.mutation<ContentPost, number>({
      query: (id) => ({ url: `/api/agent/posts/${id}/score`, method: "POST" }),
      transformResponse: (r: unknown) => unwrapData<ContentPost>(r),
      invalidatesTags: ["Posts"],
    }),
    scoreBatch: build.mutation<{ batchId: number; posts: ContentPost[] }, number>({
      query: (batchId) => ({
        url: `/api/agent/batches/${batchId}/score`,
        method: "POST",
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    repurpose: build.mutation<
      RepurposeResult & { sessionId?: number; batchId?: number },
      {
        url?: string
        pdfBase64?: string
        filename?: string
        generate?: boolean
        sessionId?: number
        preset?: string
        renderMode?: string
        imageModel?: string
      }
    >({
      query: (body) => ({ url: "/api/agent/repurpose", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts", "Sessions"],
    }),
    abSchedule: build.mutation<AbScheduleResult, { batchId: number; apply?: boolean }>({
      query: ({ batchId, apply }) => ({
        url: `/api/agent/batches/${batchId}/ab-schedule`,
        method: "POST",
        body: { apply: !!apply },
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    schedulePost: build.mutation<
      ContentPost,
      { id: number; scheduledAt?: string | null; abLabel?: string | null }
    >({
      query: ({ id, ...body }) => ({
        url: `/api/posts/${id}/schedule`,
        method: "POST",
        body,
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    getWeeklySnapshot: build.query<WeeklySnapshot, void>({
      query: () => "/api/agent/insights/weekly-snapshot",
      transformResponse: (r: unknown) => unwrapData(r),
      providesTags: ["Insights"],
    }),
    sendWeeklySnapshot: build.mutation<WeeklySnapshot, void>({
      query: () => ({
        url: "/api/agent/insights/weekly-snapshot/send",
        method: "POST",
        body: {},
      }),
      transformResponse: (r: unknown) => unwrapData(r),
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
  useUploadLogoMutation,
  useDeleteLogoMutation,
  useGetImageModelsQuery,
  useLazyPreviewTrainingQuery,
  useListSessionsQuery,
  useLazyGetSessionMessagesQuery,
  useChatMutation,
  useGenerateMutation,
  useScorePostMutation,
  useScoreBatchMutation,
  useRepurposeMutation,
  useAbScheduleMutation,
  useSchedulePostMutation,
  useGetWeeklySnapshotQuery,
  useSendWeeklySnapshotMutation,
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
