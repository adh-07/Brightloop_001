from collections.abc import Generator
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, delete

from app.core.config import settings
import app.core.db as core_db
import app.api.deps as api_deps
from app.main import app
from app.models import Item, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

# Check if configured PostgreSQL is reachable; if not, use a fast SQLite test database
_use_sqlite = False
try:
    with core_db.engine.connect() as conn:
        pass
    test_engine = core_db.engine
except Exception:
    _use_sqlite = True
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    test_engine = create_engine(
        f"sqlite:///{_tmp.name.replace('\\', '/')}",
        connect_args={"check_same_thread": False},
    )
    core_db.engine = test_engine
    api_deps.engine = test_engine


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        core_db.init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def override_db_dependency() -> Generator[None, None, None]:
    def _get_test_db() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[api_deps.get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
