from fastapi.testclient import TestClient

from app.core.config import settings


def test_quotation_template_crud_with_lines_in_one_payload(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # 1. Create a product with a variant
    prod_res = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "POS Terminal Bundle Target",
            "type": "physical",
            "sales_price": "500.00",
            "cost_price": "300.00",
            "variants": [
                {"attribute": "Color", "value": "Black", "extra_price": "0.00"}
            ],
        },
    )
    assert prod_res.status_code == 201
    prod_data = prod_res.json()
    product_id = prod_data["id"]
    variant_id = prod_data["variants"][0]["id"]

    # 2. Create quotation template with lines in single payload
    template_res = client.post(
        f"{settings.API_V1_STR}/quotation-templates/",
        headers=superuser_token_headers,
        json={
            "name": "Standard POS Package",
            "validity_days": 30,
            "is_active": True,
            "lines": [
                {
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity": 2,
                }
            ],
        },
    )
    assert template_res.status_code == 201
    template_data = template_res.json()
    assert template_data["name"] == "Standard POS Package"
    assert len(template_data["lines"]) == 1
    assert template_data["lines"][0]["quantity"] == 2

    # 3. Read back
    get_res = client.get(
        f"{settings.API_V1_STR}/quotation-templates/{template_data['id']}",
        headers=superuser_token_headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Standard POS Package"

    # 4. Update lines in single payload
    update_res = client.put(
        f"{settings.API_V1_STR}/quotation-templates/{template_data['id']}",
        headers=superuser_token_headers,
        json={
            "validity_days": 45,
            "lines": [
                {
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity": 5,
                }
            ],
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["validity_days"] == 45
    assert update_res.json()["lines"][0]["quantity"] == 5


def test_quotation_template_variant_belongs_to_product_validation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # Create product 1 with variant
    p1_res = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Product One For Template",
            "type": "software",
            "sales_price": "100.00",
            "cost_price": "20.00",
            "variants": [{"attribute": "Tier", "value": "Basic", "extra_price": "0.00"}],
        },
    )
    p1_data = p1_res.json()
    p1_variant_id = p1_data["variants"][0]["id"]

    # Create product 2
    p2_res = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": "Product Two For Template",
            "type": "software",
            "sales_price": "200.00",
            "cost_price": "40.00",
        },
    )
    p2_data = p2_res.json()
    p2_id = p2_data["id"]

    # Attempt to create quotation template using product 2 ID with product 1's variant ID
    res = client.post(
        f"{settings.API_V1_STR}/quotation-templates/",
        headers=superuser_token_headers,
        json={
            "name": "Mismatched Variant Template",
            "validity_days": 30,
            "lines": [
                {
                    "product_id": p2_id,
                    "variant_id": p1_variant_id,  # DOES NOT BELONG TO P2!
                    "quantity": 1,
                }
            ],
        },
    )
    assert res.status_code == 400
    assert "does not belong to product" in res.json()["detail"]

