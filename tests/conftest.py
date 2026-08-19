from types import SimpleNamespace
from typing import Any, Callable, Tuple

import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.factories.account import AccountFactory
from tests.factories.iscsi_client import IscsiClientFactory
from tests.factories.iscsi_cluster import IscsiClusterFactory
from tests.factories.iscsi_disk import IscsiDiskFactory
from tests.factories.iscsi_gateway import IscsiGatewayFactory
from tests.factories.iscsi_quota import IscsiQuotaFactory
from tests.factories.iscsi_targets import IscsiTargetFactory
from tests.factories.s3_quota import S3QuotaFactory
from tests.factories.s3_user import S3UserFactory
from tests.support.api_client import Api


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
            S3UserFactory,
            IscsiClusterFactory,
            IscsiQuotaFactory,
            IscsiTargetFactory,
            IscsiGatewayFactory,
            IscsiDiskFactory,
            IscsiClientFactory,
        ]:
            factory._meta.sqlalchemy_session = db.session

        def cleanup() -> None:
            db.session.remove()
            outer.rollback()
            conn.close()

        return conn, cleanup

    return SimpleNamespace(start_connection=start_connection)


@pytest.fixture(scope="session")
def api(flask_client) -> Api:
    """Return API wrapper for making HTTP requests."""
    return Api(flask_client)


@pytest.fixture(scope="package")
def s3_pools():
    """Return all S3 pools keyed by klass."""
    from tests.builders.account_namespace import load_pools

    yield load_pools("s3")


@pytest.fixture(scope="package")
def iscsi_pools():
    """Return all iSCSI pools keyed by klass."""
    from tests.builders.account_namespace import load_pools

    yield load_pools("iscsi")
