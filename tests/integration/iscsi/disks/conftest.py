import pytest

from tests.builders.ceph_namespace import CephAccountEnv, CephIscsiEnv
from tests.support.package_setup import setup_integration_package


@pytest.fixture(scope="package", autouse=True)
def integration_package(make_connection):
    yield from setup_integration_package(make_connection)


@pytest.fixture
def env(integration_package) -> CephIscsiEnv:
    env = CephIscsiEnv(package=integration_package)
    try:
        yield env
    finally:
        env.cleanup()
