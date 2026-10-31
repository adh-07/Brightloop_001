import uuid
from typing import Any
from sqlmodel import Session

from app.models import AuditLog, User


def record(
    session: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    diff: dict[str, Any] | None = None,
) -> AuditLog:
    """
    Record an audit entry for any create/update/delete action with a diff.
    """
    user_id = user.id if user else None
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        diff=diff or {},
    )
    session.add(audit_entry)
    session.commit()
    session.refresh(audit_entry)
    return audit_entry

