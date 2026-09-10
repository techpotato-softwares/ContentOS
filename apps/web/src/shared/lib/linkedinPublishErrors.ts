/** Map API error codes from LinkedIn publish to actionable Review UI copy. */
export function linkedInPublishErrorMessage(err: unknown): string {
  const data = err as {
    data?: {
      error?: { code?: string; message?: string }
      message?: string
      success?: boolean
    }
    error?: string
    message?: string
  }
  const code = data?.data?.error?.code
  const apiMessage = data?.data?.error?.message || data?.data?.message

  const byCode: Record<string, string> = {
    LINKEDIN_DISCONNECTED:
      "LinkedIn is not connected. Open Connections → LinkedIn and connect a personal profile or company page.",
    LINKEDIN_RECONNECT_REQUIRED:
      "LinkedIn session expired or was revoked. Reconnect under Connections → LinkedIn, then retry publish.",
    LINKEDIN_SCOPE_MISSING:
      "Missing LinkedIn permission. Reconnect and approve all scopes (personal: w_member_social; company: w_organization_social + r_organization_admin).",
    LINKEDIN_ORG_NOT_READY:
      "Company page is not ready. Connect the page and select which organization to publish as.",
    LINKEDIN_ORG_NOT_CONNECTED:
      "Company page OAuth is not connected. Use Connections → LinkedIn → Connect company page.",
    LINKEDIN_ORG_FORBIDDEN:
      "You cannot post as this company page. Reconnect as a page admin with posting rights.",
    LINKEDIN_ORG_SCOPES_UNAVAILABLE:
      "Company page scopes unavailable. Request Community Management API access on your LinkedIn developer app.",
    LINKEDIN_MEDIA_UNSUPPORTED:
      "LinkedIn rejected this media. Use JPEG/PNG under LinkedIn size limits, or publish carousel as a PDF document.",
    LINKEDIN_CAROUSEL_UNAVAILABLE:
      "Carousel (PDF document) publish failed. Confirm Documents API access on the LinkedIn app, or switch the post to image/text.",
    LINKEDIN_CAROUSEL_DISABLED:
      "Carousel publishing is disabled for this environment. Switch to image or text, or ask an admin to enable LINKEDIN_CAROUSEL_ENABLED.",
    CAROUSEL_EMPTY: "This carousel has no slide images. Regenerate slides before publishing.",
    LINKEDIN_RATE_LIMITED: "LinkedIn rate-limited this request. Wait a few minutes and try again.",
    REVIEW_REQUIRED: "Approve the post before publishing.",
    LINKEDIN_ERROR: apiMessage || "LinkedIn publish failed. Check connection and try again.",
  }

  if (code && byCode[code]) return byCode[code]
  if (apiMessage) return String(apiMessage)
  return "Publish to LinkedIn failed. Check connection, scopes, and media, then retry."
}
