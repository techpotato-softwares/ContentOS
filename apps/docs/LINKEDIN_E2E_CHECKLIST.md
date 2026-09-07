# LinkedIn publishing E2E verification checklist

Copy into Linear as an issue (or epic checklist). Verify each box against a real LinkedIn developer app + test accounts.

## Accounts tested
- [ ] Personal member account connected (`mode=member`, scopes include `w_member_social`)
- [ ] Company/organization page connected (`mode=organization`) + page selected
- [ ] Publish destination switcher on Review when both accounts connected (personal vs company vs auto)
- [ ] Disconnect + reconnect personal
- [ ] Disconnect + reconnect company page

## OAuth scopes
- [ ] Member: `openid profile w_member_social`
- [ ] Organization: `openid profile w_member_social w_organization_social r_organization_admin`
- [ ] Community Management API product approved on LinkedIn developer app (company flows)
- [ ] Missing-scope / revoked token shows Review UI reconnect / scope messages (`LINKEDIN_RECONNECT_REQUIRED`, `LINKEDIN_SCOPE_MISSING`, `LINKEDIN_ORG_SCOPES_UNAVAILABLE`)

## Media types
- [ ] Personal **text-only** UGC publish
- [ ] Personal **text + image** UGC publish (HTTPS or generated image URL)
- [ ] Personal **image** creative publish
- [ ] Company page **text** publish (`author` = `urn:li:organization:…`)
- [ ] Company page **image** publish
- [ ] Unsupported / unloadable media surfaces `LINKEDIN_MEDIA_UNSUPPORTED` in Review

## Carousel status
- [ ] Carousel posts stitch slides → **PDF document** via `/rest/documents` (`LINKEDIN_CAROUSEL_ENABLED=true`)
- [ ] Documents API product access confirmed on LinkedIn app
- [ ] Empty carousel slides blocked (`CAROUSEL_EMPTY`)
- [ ] With `LINKEDIN_CAROUSEL_ENABLED=false`, Review disables publish and shows clear message (`LINKEDIN_CAROUSEL_DISABLED`)
- **Ticket note:** Carousel is implemented as LinkedIn **document (PDF)** upload, not multi-image UGC. Requires Documents API; otherwise disable via env and use image/text posts.

## Scheduled publishing
- [ ] Approve post + set `scheduledAt` in the past/near future
- [ ] `scheduled_publisher` Lambda (15-min rate) picks up due approved posts
- [ ] Uses shared `execute_linkedin_publish` (same personal/org/image/carousel path as Review)
- [ ] Failure leaves post unpublished / logged in Lambda errors (no silent stub when LinkedIn is configured)
- [ ] Success sets `status=published` + `linkedin_post_id`

## Review UI
- [ ] Actionable error copy for reconnect / scopes / media / carousel / org-not-ready
- [ ] Status endpoint returns `carousel.enabled` + message
- [ ] Link to Connections → LinkedIn when disconnected
