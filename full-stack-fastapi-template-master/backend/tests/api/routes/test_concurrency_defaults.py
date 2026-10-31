import threading
from decimal import Decimal
from sqlmodel import Session, func, select

from app.models import PaymentTerm, Tax
import app.core.db as core_db


def test_concurrent_default_tax_enforcement(db: Session) -> None:
    # Create 5 taxes
    tax_ids: list[str] = []
    for i in range(5):
        t = Tax(name=f"Concurrent Tax {i}", rate=Decimal(f"{i + 5}.00"), is_default=False, is_active=True)
        db.add(t)
        db.commit()
        db.refresh(t)
        tax_ids.append(t.id)

    def set_default(tax_id: str) -> None:
        with Session(core_db.engine) as session:
            # Emulate transactionally unsetting other defaults and setting this one
            defaults = session.exec(select(Tax).where(Tax.is_default == True, Tax.id != tax_id)).all()  # noqa: E712
            for d in defaults:
                d.is_default = False
                session.add(d)
            target = session.get(Tax, tax_id)
            if target:
                target.is_default = True
                session.add(target)
            session.commit()

    threads = [threading.Thread(target=set_default, args=(tid,)) for tid in tax_ids]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    # Verify exactly one default exists among these taxes
    with Session(core_db.engine) as session:
        default_count = session.exec(
            select(func.count()).select_from(Tax).where(Tax.is_default == True, Tax.id.in_(tax_ids))  # noqa: E712
        ).one()
        assert default_count == 1


def test_concurrent_default_payment_term_enforcement(db: Session) -> None:
    # Create 5 terms
    term_ids: list[str] = []
    for i in range(5):
        pt = PaymentTerm(name=f"Concurrent Term {i}", due_days=i * 10, is_default=False)
        db.add(pt)
        db.commit()
        db.refresh(pt)
        term_ids.append(pt.id)

    def set_default(term_id: str) -> None:
        with Session(core_db.engine) as session:
            defaults = session.exec(select(PaymentTerm).where(PaymentTerm.is_default == True, PaymentTerm.id != term_id)).all()  # noqa: E712
            for d in defaults:
                d.is_default = False
                session.add(d)
            target = session.get(PaymentTerm, term_id)
            if target:
                target.is_default = True
                session.add(target)
            session.commit()

    threads = [threading.Thread(target=set_default, args=(tid,)) for tid in term_ids]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    with Session(core_db.engine) as session:
        default_count = session.exec(
            select(func.count()).select_from(PaymentTerm).where(PaymentTerm.is_default == True, PaymentTerm.id.in_(term_ids))  # noqa: E712
        ).one()
        assert default_count == 1
