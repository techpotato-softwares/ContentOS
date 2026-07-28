from __future__ import annotations
from sqlmodel import select
from decorators import Controller, Get, Post, Put, Delete
from decorators.auth_decorators import RequirePermission, RequireModule
from database import get_session
from database.models import DemoItem
from middleware.error_handler import NotFoundError, create_success_response

@Controller(path="/api/demo/items", lambda_name="demo")
class DemoItemController:
    @Post("/")
    @RequireModule("demo")
    @RequirePermission("demo:write", "admin")
    def create(self, data: dict, user=None):
        with get_session() as session:
            item = DemoItem(
                title=data["title"],
                description=data.get("description"),
                status=data.get("status", "active"),
                tenant_id=(user or {}).get("tenantId"),
                created_by=(user or {}).get("userId"),
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return create_success_response(item.model_dump(), 201)

    @Get("/")
    @RequireModule("demo")
    @RequirePermission("demo:read", "admin")
    def list(self, user=None):
        with get_session() as session:
            q = select(DemoItem)
            tid = (user or {}).get("tenantId")
            if tid is not None:
                q = q.where(DemoItem.tenant_id == tid)
            items = session.exec(q).all()
            return create_success_response([i.model_dump() for i in items])

    @Get("/{id}")
    @RequireModule("demo")
    @RequirePermission("demo:read", "admin")
    def get(self, id: str):
        with get_session() as session:
            item = session.get(DemoItem, int(id))
            if not item:
                raise NotFoundError("Demo item not found")
            return create_success_response(item.model_dump())

    @Put("/{id}")
    @RequireModule("demo")
    @RequirePermission("demo:write", "admin")
    def update(self, id: str, data: dict, user=None):
        with get_session() as session:
            item = session.get(DemoItem, int(id))
            if not item:
                raise NotFoundError("Demo item not found")
            for k in ("title", "description", "status"):
                if k in data and data[k] is not None:
                    setattr(item, k, data[k])
            item.updated_by = (user or {}).get("userId")
            session.add(item)
            session.commit()
            session.refresh(item)
            return create_success_response(item.model_dump())

    @Delete("/{id}")
    @RequireModule("demo")
    @RequirePermission("demo:write", "admin")
    def remove(self, id: str):
        with get_session() as session:
            item = session.get(DemoItem, int(id))
            if not item:
                raise NotFoundError("Demo item not found")
            session.delete(item)
            session.commit()
            return create_success_response({"deleted": True})
