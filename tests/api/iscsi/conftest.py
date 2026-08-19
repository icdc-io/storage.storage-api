import pytest

from tests.builders.iscsi_namespace import IscsiEnv
from tests.support.iscsi_service import install_iscsi_service_mock


@pytest.fixture
def env() -> IscsiEnv:
    built_env = IscsiEnv()
    try:
        yield built_env
    finally:
        built_env.cleanup()


@pytest.fixture(autouse=True)
def mocked_iscsi_service(monkeypatch):
    """Mock Ceph-backed iSCSI service for API tests by default."""
    return install_iscsi_service_mock(monkeypatch)
