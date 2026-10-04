import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def record_audit_log(
    db: Session,
    admin_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an audit log for an administrative action."""
    log_entry = AuditLog(
        admin_user_id=admin_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(log_entry)
    db.flush()
    logger.info("Audit log recorded: %s on %s:%s by admin_id=%s", action, entity_type, entity_id, admin_user_id)
    return log_entry


def list_audit_logs(
    db: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[AuditLog], int]:
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    stmt = (
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(db.scalars(stmt)), total
