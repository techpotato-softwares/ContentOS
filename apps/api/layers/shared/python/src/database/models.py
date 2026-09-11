from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, UniqueConstraint


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"
    tenant_id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)
    modules_enabled: str = Field(
        default='["platform","tenants","agent","publishing"]'
    )
    is_active: bool = True
    # Training + theme (JSON strings)
    training_json: str = Field(default="{}", sa_column=Column(Text, default="{}"))
    context_pack_cached: Optional[str] = Field(default=None, sa_column=Column(Text))
    context_pack_version: int = 0
    ui_mode: str = Field(default="platform")  # platform | white_label
    app_display_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    # First-run wizard progress (JSON text)
    onboarding_json: str = Field(default="{}", sa_column=Column(Text, default="{}"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    """App user. Tenant membership is ``tenant_id`` + ``role_id``.

    ``email_verified_at`` gates publishing. ``token_version`` invalidates JWTs
    after password reset (must match claim ``tv``).
    """

    __tablename__ = "users"
    user_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, foreign_key="tenants.tenant_id", index=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    password: str
    role_id: Optional[int] = Field(default=None, foreign_key="roles.role_id")
    is_active: bool = True
    email_verified_at: Optional[datetime] = Field(default=None, index=True)
    token_version: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuthToken(SQLModel, table=True):
    """One-time auth tokens (email verify / password reset). Store only ``token_hash``."""

    __tablename__ = "auth_tokens"
    token_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", index=True)
    purpose: str = Field(index=True)  # email_verify | password_reset
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(index=True)
    used_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    request_key: Optional[str] = Field(default=None, index=True)  # hashed email for rate limits


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    role_id: Optional[int] = Field(default=None, primary_key=True)
    role_name: str = Field(unique=True, index=True)
    description: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    permission_id: Optional[int] = Field(default=None, primary_key=True)
    permission_code: str = Field(unique=True, index=True)
    permission_name: str
    description: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    role_permission_id: Optional[int] = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="roles.role_id")
    permission_id: int = Field(foreign_key="permissions.permission_id")
    is_active: bool = True


class TrainingDocument(SQLModel, table=True):
    __tablename__ = "training_documents"
    document_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.tenant_id", index=True)
    title: str
    category: str = "other"  # product | case_study | guideline | other
    body: str = Field(sa_column=Column(Text))
    priority: int = 100
    is_active: bool = True
    created_by: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    session_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.tenant_id", index=True)
    user_id: int = Field(foreign_key="users.user_id", index=True)
    title: str = "New chat"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    message_id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.session_id", index=True)
    tenant_id: int = Field(index=True)
    role: str  # user | assistant | system
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GenerationBatch(SQLModel, table=True):
    __tablename__ = "generation_batches"
    batch_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.tenant_id", index=True)
    user_id: int = Field(foreign_key="users.user_id")
    session_id: Optional[int] = Field(default=None, foreign_key="chat_sessions.session_id")
    user_brief: str = Field(sa_column=Column(Text))
    status: str = "completed"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContentPost(SQLModel, table=True):
    __tablename__ = "content_posts"
    post_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.tenant_id", index=True)
    batch_id: Optional[int] = Field(default=None, foreign_key="generation_batches.batch_id", index=True)
    user_id: int = Field(foreign_key="users.user_id")
    angle: str  # educational | thought_leadership | product_value
    caption: str = Field(sa_column=Column(Text))
    image_prompt: str = Field(sa_column=Column(Text))
    layout_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    score_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    source_type: Optional[str] = None  # brief | url | pdf
    source_ref: Optional[str] = Field(default=None, sa_column=Column(Text))
    ab_label: Optional[str] = None  # A | B | C | hold
    image_s3_key: Optional[str] = None
    image_url: Optional[str] = None
    # draft | pending_review | approved | rejected | published
    status: str = Field(default="draft", index=True)
    linkedin_post_id: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = Field(default=None, index=True)
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SocialAccount(SQLModel, table=True):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "platform", "account_kind", name="uq_tenant_platform_kind"
        ),
    )
    account_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.tenant_id", index=True)
    platform: str = "linkedin"
    # member = personal profile; organization = Company Page
    account_kind: str = Field(default="member", index=True)
    platform_user_id: Optional[str] = None
    username: Optional[str] = None
    # Canonical LinkedIn author URN for publish (person or organization)
    author_urn: Optional[str] = None
    # Org vanity, pendingSelection, connectedBy, slide metadata, etc.
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    token_secret_arn: Optional[str] = None
    # Local/dev may store encrypted blob reference; never return raw tokens in API
    token_payload_encrypted: Optional[str] = Field(default=None, sa_column=Column(Text))
    token_expiry: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    audit_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, index=True)
    actor_user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    detail: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TenantInvite(SQLModel, table=True):
    """Team invite. ``token`` stores a SHA-256 hash of the raw secret — never the raw value."""

    __tablename__ = "tenant_invites"
    __table_args__ = (UniqueConstraint("token", name="uq_tenant_invites_token"),)
    invite_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.tenant_id", index=True)
    email: str = Field(index=True)
    role: str = Field(default="tenant_member")  # tenant_member | tenant_admin
    token: str = Field(index=True)  # sha256 hex of raw invite token
    expires_at: datetime
    invited_by: Optional[int] = Field(default=None, foreign_key="users.user_id")
    status: str = Field(default="pending", index=True)  # pending|accepted|revoked|expired
    accepted_by_user_id: Optional[int] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Keep demo table for kit compatibility (disabled in ContentOS modules by default)
class DemoItem(SQLModel, table=True):
    __tablename__ = "demo_items"
    item_id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str = "active"
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
