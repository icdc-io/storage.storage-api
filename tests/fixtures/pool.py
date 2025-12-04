import pytest

from tests.factories.pools import get_iscsi_pools, get_s3_pools


@pytest.fixture(scope="package")
def s3_pool(s3_pools):
    """Return single S3 pool 'nvme'. 'nvme' takes as default"""
    yield s3_pools["nvme"]


@pytest.fixture(scope="package")
def iscsi_pool(iscsi_pools):
    """Return single iSCSI pool 'nvme'. 'nvme' takes as default"""
    yield iscsi_pools["nvme"]


@pytest.fixture(scope="package")
def s3_pools():
    """Return all S3 pools as {klass: pool} dict."""
    yield get_s3_pools()


@pytest.fixture(scope="package")
def iscsi_pools():
    """Return all iSCSI pools as {klass: pool} dict."""
    yield get_iscsi_pools()
