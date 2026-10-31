from decimal import Decimal
from fastapi.testclient import TestClient

from app.core.config import settings


def test_product_and_variants_crud_and_odoo_effective_price(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Create product with nested variants
    res = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Connector Bridge Suite",
            "type": "software",
            "sales_price": "800.00",
            "cost_price": "200.00",
            "notes": "Third-party connector system",
            "is_active": True,
            "variants": [
                {"attribute": "Brand", "value": "Odoo", "extra_price": "560.00"},
                {"attribute": "Brand", "value": "SAP", "extra_price": "900.00"},
            ],
        },
    )
    assert res.status_code == 201
    prod_data = res.json()
    assert prod_data["name"] == "Connector Bridge Suite"
    assert len(prod_data["variants"]) == 2

    # Verify Odoo +560 effective price: 800 + 560 = 1360.00
    odoo_var = next(v for v in prod_data["variants"] if v["value"] == "Odoo")
    assert odoo_var["extra_price"] == "560.00"
    assert odoo_var["effective_price"] == "1360.00"

    product_id = prod_data["id"]

    # Add a new variant
    var_res = client.post(
        f"{settings.API_V1_STR}/products/{product_id}/variants",
        headers=superuser_token_headers,
        json={"attribute": "Brand", "value": "QuickBooks", "extra_price": "250.00"},
    )
    assert var_res.status_code == 201
    var_data = var_res.json()
    assert var_data["effective_price"] == "1050.00"  # 800 + 250 = 1050.00

    # Update variant
    var_update_res = client.put(
        f"{settings.API_V1_STR}/products/{product_id}/variants/{var_data['id']}",
        headers=superuser_token_headers,
        json={"extra_price": "300.00"},
    )
    assert var_update_res.status_code == 200
    assert var_update_res.json()["effective_price"] == "1100.00"

    # Delete variant
    var_del_res = client.delete(
        f"{settings.API_V1_STR}/products/{product_id}/variants/{var_data['id']}",
        headers=superuser_token_headers,
    )
    assert var_del_res.status_code == 200


def test_product_unique_name_among_active(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    res1 = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Unique Active Product",
            "type": "physical",
            "sales_price": "100.00",
            "cost_price": "50.00",
            "is_active": True,
        },
    )
    assert res1.status_code == 201

    # Attempt to create another active product with the exact same name -> must fail
    res2 = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Unique Active Product",
            "type": "physical",
            "sales_price": "120.00",
            "cost_price": "60.00",
            "is_active": True,
        },
    )
    assert res2.status_code == 400


def test_product_price_non_negative_validation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Negative sales_price must fail
    res = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Negative Price Product",
            "type": "service",
            "sales_price": "-10.00",
            "cost_price": "10.00",
        },
    )
    assert res.status_code in (400, 422)

