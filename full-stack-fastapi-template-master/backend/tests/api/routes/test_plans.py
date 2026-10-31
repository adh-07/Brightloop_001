from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models import BillingPeriod
from app.services.clock import FrozenClock, reset_clock, set_clock


def test_plans_crud_all_periods_and_flags(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    periods = [
        BillingPeriod.daily,
        BillingPeriod.weekly,
        BillingPeriod.monthly,
        BillingPeriod.yearly,
    ]

    for p in periods:
        res = client.post(
            f"{settings.API_V1_STR}/plans/",
            headers=superuser_token_headers,
            json={
                "name": f"Test Plan {p.value}",
                "price": "99.00",
                "billing_period": p.value,
                "min_quantity": 2,
                "available_from": "2026-01-01",
                "available_to": "2026-12-31",
                "auto_close": True,
                "closable": True,
                "pausable": False,
                "renewable": True,
                "is_active": True,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["billing_period"] == p.value
        assert data["auto_close"] is True
        assert data["pausable"] is False

        # Read back
        get_res = client.get(
            f"{settings.API_V1_STR}/plans/{data['id']}",
            headers=superuser_token_headers,
        )
        assert get_res.status_code == 200
        assert get_res.json()["name"] == f"Test Plan {p.value}"

        # Delete
        del_res = client.delete(
            f"{settings.API_V1_STR}/plans/{data['id']}",
            headers=superuser_token_headers,
        )
        assert del_res.status_code == 200


def test_plan_date_validation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # available_to < available_from must fail with 422/400
    res = client.post(
        f"{settings.API_V1_STR}/plans/",
        headers=superuser_token_headers,
        json={
            "name": "Invalid Date Plan",
            "price": "50.00",
            "billing_period": "monthly",
            "min_quantity": 1,
            "available_from": "2026-06-01",
            "available_to": "2026-05-31",
        },
    )
    assert res.status_code in (400, 422)


def test_plan_is_available_today_injectable_clock(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Create a plan valid from 2026-05-01 to 2026-05-31
    res = client.post(
        f"{settings.API_V1_STR}/plans/",
        headers=superuser_token_headers,
        json={
            "name": "May Only Plan",
            "price": "10.00",
            "billing_period": "monthly",
            "min_quantity": 1,
            "available_from": "2026-05-01",
            "available_to": "2026-05-31",
            "is_active": True,
        },
    )
    assert res.status_code == 201
    plan_id = res.json()["id"]

    try:
        # 1. Before available_from -> False
        set_clock(FrozenClock(current_date=date(2026, 4, 30)))
        res1 = client.get(
            f"{settings.API_V1_STR}/plans/{plan_id}",
            headers=superuser_token_headers,
        )
        assert res1.json()["is_available_today"] is False

        # 2. Inside window -> True
        set_clock(FrozenClock(current_date=date(2026, 5, 15)))
        res2 = client.get(
            f"{settings.API_V1_STR}/plans/{plan_id}",
            headers=superuser_token_headers,
        )
        assert res2.json()["is_available_today"] is True

        # 3. After available_to -> False
        set_clock(FrozenClock(current_date=date(2026, 6, 1)))
        res3 = client.get(
            f"{settings.API_V1_STR}/plans/{plan_id}",
            headers=superuser_token_headers,
        )
        assert res3.json()["is_available_today"] is False
    finally:
        reset_clock()

