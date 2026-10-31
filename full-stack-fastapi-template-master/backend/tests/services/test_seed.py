from sqlmodel import Session

from app.seed.catalog import seed_catalog


def test_seed_catalog_idempotency(db: Session) -> None:
    # Run 1
    counts1 = seed_catalog(db)
    assert counts1["products"] >= 8
    assert counts1["plans"] >= 4
    assert counts1["taxes"] >= 3
    assert counts1["payment_terms"] >= 3
    assert counts1["discounts"] >= 4
    assert counts1["quotation_templates"] >= 3

    # Run 2 (must be strictly idempotent)
    counts2 = seed_catalog(db)
    assert counts1 == counts2

