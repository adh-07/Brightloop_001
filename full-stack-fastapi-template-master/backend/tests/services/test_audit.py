from decimal import Decimal
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import AuditLog


def test_audit_entries_written_for_all_mutations(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    # 1. Create product -> audit create
    prod_res = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Audit Tracked Product",
            "type": "software",
            "sales_price": "250.00",
            "cost_price": "50.00",
        },
    )
    assert prod_res.status_code == 201
    prod_id = prod_res.json()["id"]

    create_log = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "product",
            AuditLog.entity_id == prod_id,
            AuditLog.action == "create",
        )
    ).first()
    assert create_log is not None
    assert create_log.diff["name"] == "Audit Tracked Product"

    # 2. Update product -> audit update
    update_res = client.put(
        f"{settings.API_V1_STR}/products/{prod_id}",
        headers=superuser_token_headers,
        json={"sales_price": "300.00"},
    )
    assert update_res.status_code == 200

    update_log = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "product",
            AuditLog.entity_id == prod_id,
            AuditLog.action == "update",
        )
    ).first()
    assert update_log is not None
    assert "sales_price" in update_log.diff
    assert update_log.diff["sales_price"]["new"] == "300.00"

    # 3. Delete product -> audit delete
    del_res = client.delete(
        f"{settings.API_V1_STR}/products/{prod_id}",
        headers=superuser_token_headers,
    )
    assert del_res.status_code == 200

    del_log = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "product",
            AuditLog.entity_id == prod_id,
            AuditLog.action == "delete",
        )
    ).first()
    assert del_log is not None
    assert del_log.diff["name"] == "Audit Tracked Product"

