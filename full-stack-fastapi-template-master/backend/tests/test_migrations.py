from pathlib import Path
import shutil
import tempfile
from alembic import command
from alembic.config import Config


def test_migrations_from_empty_and_phase1() -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"

    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(tmp_dir) / "test_migration.db"
        db_url = f"sqlite:///{db_path.as_posix()}"

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # 1. Upgrade from empty DB up to phase-1 revision
        command.upgrade(alembic_cfg, "p1_roles_audit")

        # 2. Upgrade from phase-1 revision to phase-2 revision (head)
        command.upgrade(alembic_cfg, "head")

        # 3. Downgrade back to phase-1
        command.downgrade(alembic_cfg, "p1_roles_audit")

        # 4. Upgrade back to head
        command.upgrade(alembic_cfg, "head")

        # 5. Downgrade to base
        command.downgrade(alembic_cfg, "base")

        # 6. Upgrade from empty to head all in one step
        command.upgrade(alembic_cfg, "head")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
