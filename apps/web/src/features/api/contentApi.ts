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

export type TenantInviteRow = {
  inviteId: number
  email: string
  role: string
  status: string
  expiresAt?: string | null
  invitedBy?: number | null
  tenantId?: number
  tenantName?: string | null
  createdAt?: string | null
  acceptedAt?: string | null
}

export type TenantInvitePreview = {
  email: string
  role: string
  expiresAt?: string | null
  tenantName?: string | null
  status: string
}

export type TenantInviteAcceptResult = {
  accepted: boolean
  registered?: boolean
  tenantId?: number
  role?: string
  accessToken: string
  refreshToken: string
  user: {
    userId: number
    username: string
    email?: string | null
    roleName?: string | null
    tenantId?: number | null
    permissions?: string[]
    modulesEnabled?: string[]
    emailVerified?: boolean
  }
}

export type AiSettingsPayload = {
  aiBillingMode: "platform" | "byok" | string
  planTier: string
  byokAllowed: boolean
  quota: {
    monthlyLimit: number
    usedThisMonth: number
    month: string
    remaining: number
  }
  keys: {
    openaiConfigured: boolean
    geminiConfigured: boolean
  }
  plans: Array<{
    id: string
    label: string
    monthlyUsd: number
    quota: number
    byokAllowed: boolean
  }>
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
  format?: "text" | "image" | "carousel" | string
  hashtags?: string[]
  attachedImage?: boolean
  slides?: Array<{
    headline?: string
    body?: string
    imageUrl?: string
    visual_prompt?: string
  }>
  layout?: {
    format?: string
    headline?: string
    subhead?: string
    bullets?: string[]
    caption?: string
    hashtags?: string[]
    attachedImage?: boolean
    slides?: Array<{
      headline?: string
      body?: string
      imageUrl?: string
    }>
  }
  score?: PostScore
  sourceType?: string
  sourceRef?: string
  abLabel?: string
  scheduledAt?: string | null
  publishedAt?: string | null
}

export type LinkedInAccountStatus = {
  connected: boolean
  pendingSelection?: boolean
  username?: string
  platformUserId?: string
  authorUrn?: string
  expiresAt?: string | null
  metadata?: Record<string, string | undefined>
}

export type LinkedInStatus = {
  connected: boolean
  username?: string
  expiresAt?: string | null
  member: LinkedInAccountStatus
  organization: LinkedInAccountStatus
}

export type LinkedInOrganization = {
  organizationId: string
  organizationUrn: string
  name: string
  vanityName?: string | null
  role?: string
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

export type GenerationBatchRow = {
  batchId: number
  brief?: string
  createdAt?: string | null
  status?: string
  posts: ContentPost[]
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

export type TextProviderInfo = {
  id: string
  label: string
  model: string
  available: boolean
  default?: boolean
}

export type ImageModelsPayload = {
  models: ImageModelInfo[]
  presets: { id: string; width: number; height: number }[]
  defaultPreset: string
  defaultRenderMode: string
  textProviders?: TextProviderInfo[]
  defaultTextProvider?: string
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
  tagTypes: [
    "Theme",
    "Training",
    "Tenants",
    "TenantInvites",
    "Posts",
    "LinkedIn",
    "Batch",
    "Sessions",
    "Insights",
    "Billing",
    "AiSettings",
  ],
  endpoints: (build) => ({
    getTheme: build.query<ThemePayload, void>({
      query: () => "/api/tenants/me/theme",
      transformResponse: (r: unknown) => unwrapData<ThemePayload>(r),
      providesTags: ["Theme"],
    }),
    createCheckoutSession: build.mutation<
      { url: string; sessionId: string },
      { planTier: string; successUrl?: string; cancelUrl?: string }
    >({
      query: (body) => ({ url: "/api/billing/checkout-session", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    createPortalSession: build.mutation<{ url: string }, void>({
      query: () => ({ url: "/api/billing/portal-session", method: "POST", body: {} }),
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    getAiSettings: build.query<AiSettingsPayload, void>({
      query: () => "/api/tenants/me/ai-settings",
      transformResponse: (r: unknown) => unwrapData<AiSettingsPayload>(r),
      providesTags: ["AiSettings"],
    }),
    putAiSettings: build.mutation<
      AiSettingsPayload,
      {
        aiBillingMode?: "platform" | "byok"
        openaiApiKey?: string
        geminiApiKey?: string
        clearOpenai?: boolean
        clearGemini?: boolean
      }
    >({
      query: (body) => ({ url: "/api/tenants/me/ai-settings", method: "PUT", body }),
      transformResponse: (r: unknown) => unwrapData<AiSettingsPayload>(r),
      invalidatesTags: ["AiSettings", "Billing"],
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
    listTenantInvites: build.query<{ invites: TenantInviteRow[] }, void>({
      query: () => "/api/tenants/invites",
      transformResponse: (r: unknown) => unwrapData<{ invites: TenantInviteRow[] }>(r),
      providesTags: ["TenantInvites"],
    }),
    createTenantInvite: build.mutation<
      { invite: TenantInviteRow; emailSent: boolean; emailReason?: string },
      { email: string; role?: "tenant_member" | "tenant_admin" }
    >({
      query: (body) => ({ url: "/api/tenants/invites", method: "POST", body }),
      transformResponse: (r: unknown) =>
        unwrapData<{ invite: TenantInviteRow; emailSent: boolean; emailReason?: string }>(r),
      invalidatesTags: ["TenantInvites"],
    }),
    revokeTenantInvite: build.mutation<
      { invite: TenantInviteRow; revoked: boolean },
      number
    >({
      query: (inviteId) => ({
        url: `/api/tenants/invites/${inviteId}`,
        method: "DELETE",
      }),
      transformResponse: (r: unknown) =>
        unwrapData<{ invite: TenantInviteRow; revoked: boolean }>(r),
      invalidatesTags: ["TenantInvites"],
    }),
    previewTenantInvite: build.query<TenantInvitePreview, string>({
      query: (token) => `/api/tenants/invites/preview?token=${encodeURIComponent(token)}`,
      transformResponse: (r: unknown) => unwrapData<TenantInvitePreview>(r),
    }),
    acceptTenantInvite: build.mutation<
      TenantInviteAcceptResult,
      { token: string; username?: string; email?: string; password?: string }
    >({
      query: (body) => ({ url: "/api/tenants/invites/accept", method: "POST", body }),
      transformResponse: (r: unknown) => unwrapData<TenantInviteAcceptResult>(r),
      invalidatesTags: ["TenantInvites"],
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
        batches?: GenerationBatchRow[]
      },
      number
    >({
      query: (sessionId) => `/api/agent/sessions/${sessionId}/messages`,
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    chat: build.mutation<
      { sessionId: number; reply: string; provider?: string },
      { message: string; sessionId?: number; aiProvider?: string }
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
        format?: string
        renderMode?: string
        imageModel?: string
        sourceType?: string
        aiProvider?: string
      },
      {
        brief: string
        sessionId?: number
        newsContext?: string
        preset?: string
        format?: "text" | "image" | "carousel"
        attachImage?: boolean
        renderMode?: string
        imageModel?: string
        aiProvider?: string
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
        userContext?: string
        format?: "text" | "image" | "carousel"
        attachImage?: boolean
        sessionId?: number
        preset?: string
        renderMode?: string
        imageModel?: string
        aiProvider?: string
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
    publishPost: build.mutation<
      ContentPost,
      number | { id: number; publishAs?: "member" | "organization" }
    >({
      query: (arg) => {
        const id = typeof arg === "number" ? arg : arg.id
        const body =
          typeof arg === "number" ? {} : { publishAs: arg.publishAs }
        return { url: `/api/posts/${id}/publish`, method: "POST", body }
      },
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    quickPublishPost: build.mutation<
      ContentPost,
      number | { id: number; publishAs?: "member" | "organization" }
    >({
      query: (arg) => {
        const id = typeof arg === "number" ? arg : arg.id
        const body =
          typeof arg === "number" ? {} : { publishAs: arg.publishAs }
        return { url: `/api/posts/${id}/quick-publish`, method: "POST", body }
      },
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["Posts"],
    }),
    linkedInStatus: build.query<LinkedInStatus, { tenantId?: number } | void>({
      query: (arg) => {
        const tid = arg && typeof arg === "object" ? arg.tenantId : undefined
        return tid
          ? `/api/social/linkedin/status?tenantId=${tid}`
          : "/api/social/linkedin/status"
      },
      transformResponse: (r: unknown) => unwrapData(r),
      providesTags: ["LinkedIn"],
    }),
    linkedInConnect: build.mutation<
      { authorizeUrl: string; mode: string },
      { mode?: "member" | "organization"; tenantId?: number }
    >({
      query: (arg) => {
        const params = new URLSearchParams()
        params.set("mode", arg?.mode || "member")
        if (arg?.tenantId) params.set("tenantId", String(arg.tenantId))
        return {
          url: `/api/social/linkedin/connect?${params.toString()}`,
          method: "GET",
        }
      },
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    linkedInOrganizations: build.query<
      { organizations: LinkedInOrganization[] },
      { tenantId?: number } | void
    >({
      query: (arg) => {
        const tid = arg && typeof arg === "object" ? arg.tenantId : undefined
        return tid
          ? `/api/social/linkedin/organizations?tenantId=${tid}`
          : "/api/social/linkedin/organizations"
      },
      transformResponse: (r: unknown) => unwrapData(r),
    }),
    linkedInSelectOrganization: build.mutation<
      LinkedInAccountStatus,
      {
        organizationId: string
        name?: string
        vanityName?: string
        tenantId?: number
      }
    >({
      query: (body) => ({
        url: "/api/social/linkedin/organizations/select",
        method: "POST",
        body,
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["LinkedIn"],
    }),
    linkedInDisconnect: build.mutation<
      { disconnected: boolean; accountKind: string },
      { accountKind: "member" | "organization"; tenantId?: number }
    >({
      query: (body) => ({
        url: "/api/social/linkedin/disconnect",
        method: "POST",
        body,
      }),
      transformResponse: (r: unknown) => unwrapData(r),
      invalidatesTags: ["LinkedIn"],
    }),
  }),
})

export const {
  useGetThemeQuery,
  useCreateCheckoutSessionMutation,
  useCreatePortalSessionMutation,
  useGetAiSettingsQuery,
  usePutAiSettingsMutation,
  useListTenantsQuery,
  useCreateTenantMutation,
  useListTenantInvitesQuery,
  useCreateTenantInviteMutation,
  useRevokeTenantInviteMutation,
  usePreviewTenantInviteQuery,
  useAcceptTenantInviteMutation,
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
  useQuickPublishPostMutation,
  useLinkedInStatusQuery,
  useLinkedInConnectMutation,
  useLazyLinkedInOrganizationsQuery,
  useLinkedInSelectOrganizationMutation,
  useLinkedInDisconnectMutation,
} = contentApi
