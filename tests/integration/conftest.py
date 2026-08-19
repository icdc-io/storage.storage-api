import pytest

from tests.builders.ceph_namespace import CephAccountEnv

pytestmark = [pytest.mark.integration, pytest.mark.ceph]


@pytest.fixture
def ceph_env(integration_package) -> CephAccountEnv:
    """Real Ceph-backed builder namespace for integration tests."""
    env = CephAccountEnv(package=integration_package)
    try:
        yield env
    finally:
        env.cleanup()
