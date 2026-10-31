from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.user import get_token_headers_for_role


def test_permission_matrix_all_write_endpoints(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    admin_headers = superuser_token_headers
    staff_headers = get_token_headers_for_role(client, db, "staff")
    customer_headers = get_token_headers_for_role(client, db, "customer")
    anon_headers: dict[str, str] = {}

    write_endpoints_payloads = [
        # Products
        (
            "POST",
            f"{settings.API_V1_STR}/products/",
            {
                "name": "Permission Test Product",
                "type": "software",
                "sales_price": "100.00",
                "cost_price": "20.00",
            },
        ),
        # Plans
        (
            "POST",
            f"{settings.API_V1_STR}/plans/",
            {
                "name": "Permission Test Plan",
                "price": "29.00",
                "billing_period": "monthly",
                "available_from": "2026-01-01",
            },
        ),
        # Taxes
        (
            "POST",
            f"{settings.API_V1_STR}/taxes/",
            {
                "name": "Permission Test Tax",
                "rate": "15.00",
            },
        ),
        # Payment terms
        (
            "POST",
            f"{settings.API_V1_STR}/payment-terms/",
            {
                "name": "Permission Test Term",
                "due_days": 45,
            },
        ),
        # Discounts
        (
            "POST",
            f"{settings.API_V1_STR}/discounts/",
            {
                "name": "Permission Test Discount",
                "kind": "percent",
                "value": "10.00",
                "scope": "subscription",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        ),
        # Quotation templates
        (
            "POST",
            f"{settings.API_V1_STR}/quotation-templates/",
            {
                "name": "Permission Test Template",
                "validity_days": 30,
                "lines": [],
            },
        ),
    ]

    for method, url, payload in write_endpoints_payloads:
        # Anonymous -> 401
        res_anon = client.request(method, url, headers=anon_headers, json=payload)
        assert res_anon.status_code == 401, f"{url} expected 401 for anonymous, got {res_anon.status_code}"

        # Customer -> 403
        res_cust = client.request(method, url, headers=customer_headers, json=payload)
        assert res_cust.status_code == 403, f"{url} expected 403 for customer, got {res_cust.status_code}"

        # Staff -> 403 on write endpoints
        res_staff = client.request(method, url, headers=staff_headers, json=payload)
        assert res_staff.status_code == 403, f"{url} expected 403 for staff, got {res_staff.status_code}"

        # Admin -> 2xx
        res_admin = client.request(method, url, headers=admin_headers, json=payload)
        assert res_admin.status_code in (200, 201), f"{url} expected 2xx for admin, got {res_admin.status_code}"


def test_permission_catalog_read_access(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    admin_headers = superuser_token_headers
    staff_headers = get_token_headers_for_role(client, db, "staff")
    customer_headers = get_token_headers_for_role(client, db, "customer")

    catalog_read_endpoints = [
        f"{settings.API_V1_STR}/products/",
        f"{settings.API_V1_STR}/plans/",
        f"{settings.API_V1_STR}/quotation-templates/",
    ]

    for url in catalog_read_endpoints:
        # Staff can read catalog
        res_staff = client.get(url, headers=staff_headers)
        assert res_staff.status_code == 200, f"{url} expected 200 for staff, got {res_staff.status_code}"

        # Admin can read catalog
        res_admin = client.get(url, headers=admin_headers)
        assert res_admin.status_code == 200, f"{url} expected 200 for admin, got {res_admin.status_code}"


def test_permission_discounts_admin_only(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """Discounts completely invisible/forbidden to staff and customers (read and write)."""
    admin_headers = superuser_token_headers
    staff_headers = get_token_headers_for_role(client, db, "staff")
    customer_headers = get_token_headers_for_role(client, db, "customer")

    url = f"{settings.API_V1_STR}/discounts/"

    # Staff gets 403 on discounts read
    res_staff = client.get(url, headers=staff_headers)
    assert res_staff.status_code == 403

    # Customer gets 403 on discounts read
    res_cust = client.get(url, headers=customer_headers)
    assert res_cust.status_code == 403

    # Admin gets 200 on discounts read
    res_admin = client.get(url, headers=admin_headers)
    assert res_admin.status_code == 200


def test_permission_config_endpoints_customer_forbidden(
    client: TestClient, db: Session
) -> None:
    """Customers get 403 on config endpoints."""
    customer_headers = get_token_headers_for_role(client, db, "customer")

    config_endpoints = [
        f"{settings.API_V1_STR}/taxes/",
        f"{settings.API_V1_STR}/payment-terms/",
        f"{settings.API_V1_STR}/discounts/",
    ]

    for url in config_endpoints:
        res = client.get(url, headers=customer_headers)
        assert res.status_code == 403, f"{url} expected 403 for customer, got {res.status_code}"

