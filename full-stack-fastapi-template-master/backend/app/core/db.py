from sqlmodel import SQLModel, Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserRole

db_url = str(settings.DATABASE_URL)
if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url, pool_pre_ping=True)


def init_db(session: Session) -> None:
    if db_url.startswith("sqlite"):
        SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            role=UserRole.admin.value,
        )
        user = crud.create_user(session=session, user_create=user_in)
    elif user.role != UserRole.admin.value or not user.is_superuser:
        user.role = UserRole.admin.value
        user.is_superuser = True
        session.add(user)
        session.commit()
