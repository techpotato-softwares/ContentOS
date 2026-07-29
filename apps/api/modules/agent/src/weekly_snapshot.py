"""Build and send weekly team performance snapshot emails via SES."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlmodel import select
from database import get_session
from database.models import Tenant, User, Role, ContentPost, GenerationBatch, AuditLog
from utils.ses_mail import send_email
from utils.logger import logger


def _week_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    end = now or datetime.utcnow()
    start = end - timedelta(days=7)
    return start, end


def collect_tenant_stats(session, tenant_id: int, start: datetime, end: datetime) -> dict:
    posts = session.exec(
        select(ContentPost).where(
            ContentPost.tenant_id == tenant_id,
            ContentPost.created_at >= start,
            ContentPost.created_at <= end,
        )
    ).all()
    published = [p for p in posts if p.status == "published"]
    approved = [p for p in posts if p.status == "approved"]
    drafts = [p for p in posts if p.status == "draft"]
    pending = [p for p in posts if p.status == "pending_review"]
    upcoming = session.exec(
        select(ContentPost).where(
            ContentPost.tenant_id == tenant_id,
            ContentPost.scheduled_at != None,  # noqa: E711
        )
    ).all()
    scheduled = [
        p
        for p in upcoming
        if p.status in ("draft", "pending_review", "approved") and p.scheduled_at
    ]

    batches = session.exec(
        select(GenerationBatch).where(
            GenerationBatch.tenant_id == tenant_id,
            GenerationBatch.created_at >= start,
            GenerationBatch.created_at <= end,
        )
    ).all()

    by_angle: dict[str, int] = {}
    for p in posts:
        by_angle[p.angle] = by_angle.get(p.angle, 0) + 1

    top = None
    for p in published or approved or posts:
        if p.caption:
            top = {
                "postId": p.post_id,
                "angle": p.angle,
                "status": p.status,
                "headline": _headline(p),
                "captionPreview": (p.caption or "")[:160],
            }
            break

    audits = session.exec(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= start,
            AuditLog.created_at <= end,
        )
    ).all()

    return {
        "generated": len(posts),
        "batches": len(batches),
        "draft": len(drafts),
        "pendingReview": len(pending),
        "approved": len(approved),
        "published": len(published),
        "scheduledUpcoming": len(scheduled),
        "byAngle": by_angle,
        "topPost": top,
        "auditEvents": len(audits),
        "periodStart": start.isoformat() + "Z",
        "periodEnd": end.isoformat() + "Z",
    }


def _headline(p: ContentPost) -> str:
    if p.layout_json:
        try:
            import json

            layout = json.loads(p.layout_json)
            if layout.get("headline"):
                return layout["headline"]
        except Exception:
            pass
    return (p.caption or "").split("\n", 1)[0][:80]


def _admin_emails(session, tenant_id: int) -> list[str]:
    roles = session.exec(select(Role)).all()
    role_ids = {
        r.role_id
        for r in roles
        if r.role_name in ("tenant_admin", "super_admin")
    }
    users = session.exec(
        select(User).where(
            User.tenant_id == tenant_id,
            User.is_active == True,  # noqa: E712
        )
    ).all()
    emails = []
    for u in users:
        if u.role_id in role_ids and u.email:
            emails.append(u.email)
    # Fallback: any active user on tenant
    if not emails:
        emails = [u.email for u in users if u.email]
    return sorted(set(emails))


def render_snapshot_email(tenant_name: str, stats: dict) -> tuple[str, str, str]:
    subject = f"ContentOS weekly snapshot — {tenant_name}"
    top = stats.get("topPost") or {}
    angles = ", ".join(f"{k}: {v}" for k, v in (stats.get("byAngle") or {}).items()) or "—"
    text = (
        f"Weekly performance for {tenant_name}\n"
        f"Period: {stats.get('periodStart')} → {stats.get('periodEnd')}\n\n"
        f"Generated posts: {stats['generated']} (batches: {stats['batches']})\n"
        f"Draft: {stats['draft']} | In review: {stats['pendingReview']} | "
        f"Approved: {stats['approved']} | Published: {stats['published']}\n"
        f"Scheduled upcoming: {stats['scheduledUpcoming']}\n"
        f"By angle: {angles}\n"
        f"Audit events: {stats['auditEvents']}\n"
    )
    if top:
        text += (
            f"\nHighlight: #{top.get('postId')} [{top.get('angle')}] "
            f"{top.get('headline') or top.get('captionPreview')}\n"
        )
    text += (
        "\nNext week tips:\n"
        "- Aim for 3–4 LinkedIn image posts\n"
        "- Mix educational + product value angles\n"
        "- Score drafts before publish and apply A/B schedule slots\n"
    )

    html = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;color:#0f172a;line-height:1.5">
  <h1 style="font-size:22px">Weekly snapshot — {tenant_name}</h1>
  <p style="color:#64748b;font-size:13px">
    {stats.get('periodStart')} → {stats.get('periodEnd')}
  </p>
  <table style="border-collapse:collapse;width:100%;max-width:560px">
    <tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">Generated</td>
        <td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right"><b>{stats['generated']}</b></td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">Batches</td>
        <td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right">{stats['batches']}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">Draft / Review / Approved / Published</td>
        <td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right">
          {stats['draft']} / {stats['pendingReview']} / {stats['approved']} / {stats['published']}
        </td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">Scheduled upcoming</td>
        <td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right">{stats['scheduledUpcoming']}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">Angles</td>
        <td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right">{angles}</td></tr>
  </table>
  {f'<p style="margin-top:20px"><b>Highlight</b><br/>#{top.get("postId")} · {top.get("angle")}<br/>{top.get("headline") or top.get("captionPreview")}</p>' if top else ''}
  <p style="margin-top:24px;font-size:13px;color:#475569">
    Next week: generate 3–4 posts, score before publish, and apply A/B schedule suggestions.
  </p>
  <p style="font-size:12px;color:#94a3b8">Sent by ContentOS via Amazon SES</p>
</body></html>"""
    return subject, html, text


def send_weekly_snapshots(*, tenant_id: int | None = None) -> dict:
    """Send weekly emails for one tenant or all active tenants."""
    start, end = _week_window()
    results = []
    with get_session() as session:
        q = select(Tenant).where(Tenant.is_active == True)  # noqa: E712
        if tenant_id is not None:
            q = q.where(Tenant.tenant_id == tenant_id)
        tenants = session.exec(q).all()
        for tenant in tenants:
            stats = collect_tenant_stats(session, tenant.tenant_id, start, end)  # type: ignore[arg-type]
            emails = _admin_emails(session, tenant.tenant_id)  # type: ignore[arg-type]
            subject, html, text = render_snapshot_email(tenant.name, stats)
            if not emails:
                logger.warn(
                    "No admin emails for tenant snapshot",
                    {"tenantId": tenant.tenant_id},
                )
                results.append(
                    {
                        "tenantId": tenant.tenant_id,
                        "tenantName": tenant.name,
                        "stats": stats,
                        "email": {"sent": False, "reason": "no_recipients"},
                    }
                )
                continue
            email_result = send_email(
                to_addresses=emails,
                subject=subject,
                html_body=html,
                text_body=text,
            )
            results.append(
                {
                    "tenantId": tenant.tenant_id,
                    "tenantName": tenant.name,
                    "stats": stats,
                    "email": email_result,
                }
            )
    return {
        "periodStart": start.isoformat() + "Z",
        "periodEnd": end.isoformat() + "Z",
        "tenants": results,
    }
