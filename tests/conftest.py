import sys
import types
import pytest


@pytest.fixture(scope="session", autouse=True)
def mock_missing_ceph_libraries():
    sys.modules["rados"] = types.ModuleType("rados")
    sys.modules["rbd"] = types.ModuleType("rbd")
    # Optionally, add attributes/methods to the mock module if needed
    # sys.modules["missing_lib"].some_function = lambda *a, **kw: None

@pytest.fixture(scope="session")
def client():
    from main import flask_app
    from app.seed import get_or_create_account
    flask_app.testing = True
    with flask_app.app_context():
        get_or_create_account("devel","devel account")
        yield flask_app.test_client()


@pytest.fixture(scope="module")
def valid_headers():
    return {
        "x-auth-account": "devel",
        "x-auth-role": "admin",
        "Content-Type": "application/json",
    }