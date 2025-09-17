from types import SimpleNamespace

import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.api import Api
from tests.factory.account import AccountFactory
from tests.factory.headers import HeadersFactory
from tests.factory.s3_quota import S3QuotaFactory


@pytest.fixture(scope="session", autouse=True)
def app():
    from main import create_app
    app = create_app()
    with app.app_context():
        from app.seed import seed
        seed()
        yield app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="package")
def make_connection(app):
    def start_connection():
        from app.database import db
        conn = db.engine.connect()
        outer = conn.begin()
        Session = sessionmaker(bind=conn, future=True, expire_on_commit=True, autoflush=True, join_transaction_mode="create_savepoint")
        db.session.remove()
        db.session = scoped_session(Session)

        AccountFactory._meta.sqlalchemy_session = db.session
        S3QuotaFactory._meta.sqlalchemy_session = db.session

        def cleanup():
            db.session.remove()
            outer.rollback()
            conn.close()

        return conn, cleanup
    return SimpleNamespace(start_connection=start_connection)


@pytest.fixture
def ceph_cleanup_registry():
    undos = []
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
    undos = []
    try:
        yield undos
    finally:
        for undo in reversed(undos):
            try:
                undo()
            except Exception:
                pass


@pytest.fixture
def headers_factory():
    return HeadersFactory


@pytest.fixture(scope="package")
def headers_factory_scope_package():
    return HeadersFactory


@pytest.fixture(scope="session")
def api(client):
    return Api(client)
