import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Tuple

import pytest
import yaml
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.api import Api
from tests.factories.account import AccountFactory
from tests.factories.iscsi_client import IscsiAssignedClientFactory, IscsiClientFactory
from tests.factories.iscsi_cluster import IscsiClusterFactory
from tests.factories.iscsi_disk import IscsiDiskCephFactory, IscsiDiskFactory
from tests.factories.iscsi_gateway import IscsiGatewayFactory
from tests.factories.iscsi_quota import IscsiQuotaFactory
from tests.factories.iscsi_targets import IscsiTargetFactory
from tests.factories.s3_quota import S3QuotaFactory


@pytest.fixture(scope="session", autouse=True)
def app():
    """Create Flask app once per session and seed database."""
    from main import create_app
    app = create_app()
    with app.app_context():
        from app.seed import seed
        seed()
        yield app


@pytest.fixture(scope="session")
def flask_client(app):
    """Return Flask test client."""
    return app.test_client()


@pytest.fixture(scope="package")
def make_connection(app):
    """Create DB connection with rollback + bind to factories."""

    def start_connection() -> Tuple[Any, Callable[[], None]]:
        from app.database import db
        conn = db.engine.connect()
        outer = conn.begin()
        Session = sessionmaker(
            bind=conn,
            future=True,
            expire_on_commit=True,
            autoflush=True,
            join_transaction_mode="create_savepoint",
        )

        # Replace global session
        db.session.remove()
        db.session = scoped_session(Session)

        # Bind all factories
        for factory in [
            AccountFactory,
            S3QuotaFactory,
            IscsiClusterFactory,
            IscsiQuotaFactory,
            IscsiTargetFactory,
            IscsiGatewayFactory,
            IscsiDiskFactory,
            IscsiDiskCephFactory,
            IscsiClientFactory,
            IscsiAssignedClientFactory
        ]:
            factory._meta.sqlalchemy_session = db.session

        def cleanup() -> None:
            db.session.remove()
            outer.rollback()
            conn.close()

        return conn, cleanup

    return SimpleNamespace(start_connection=start_connection)


class ObjectCleaner:
    def __init__(self):
        self.to_delete = []

    def delete(self, model, objects=None, ids=None, immediate=False):
        if ids:
            if isinstance(ids, (int, str)):
                obj = model.query.filter_by(id=ids).first()
                if obj:
                    objects = [obj]
            else:
                objects = model.query.filter(model.id.in_(ids)).all()
        elif objects:
            if isinstance(objects, model):
                objects = [objects]
            objects = objects or []

        if not objects:
            return

        if immediate:
            for obj in objects:
                obj.destroy()
            return

        self.to_delete.extend(objects)

    def finalize(self):
        for obj in self.to_delete:
            obj.destroy()


@pytest.fixture
def cleaner():
    c = ObjectCleaner()
    yield c
    c.finalize()


def get_environment_data(filename: str = None) -> dict:
    """Load YAML config for test environment."""
    env_file = os.getenv("FIXTURES_FILE")
    path_str = env_file or filename

    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@pytest.fixture(scope="session")
def env_data() -> dict:
    """Return parsed environment config."""
    return get_environment_data()


@pytest.fixture
def ceph_cleanup_registry():
    """Register cleanup callbacks and run them in reverse after test."""
    undos: list[Callable[[], None]] = []
    try:
        yield undos
    finally:
        for undo in reversed(undos):
            try:
                undo()
            except Exception:
                pass


@pytest.fixture(scope="package")
def ceph_cleanup_registry_scope_package():
    """Same as above but package-scoped."""
    undos: list[Callable[[], None]] = []
    try:
        yield undos
    finally:
        for undo in reversed(undos):
            try:
                undo()
            except Exception:
                pass


@pytest.fixture(scope="session")
def api(flask_client) -> Api:
    """Return API wrapper for making HTTP requests."""
    return Api(flask_client)
