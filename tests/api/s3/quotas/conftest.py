import pytest

from tests.support.package_setup import setup_api_package


@pytest.fixture(scope="package", autouse=True)
def api_s3_quotas_package(make_connection):
    yield from setup_api_package(make_connection)


@pytest.fixture
def mocked_s3_quota_service(fake_s3_ceph):
    return fake_s3_ceph.states
