import pytest

from tests.support.package_setup import setup_api_package


@pytest.fixture(scope="package", autouse=True)
def api_iscsi_disks_package(make_connection):
    yield from setup_api_package(make_connection)
