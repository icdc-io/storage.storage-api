import pytest

from tests.factories.s3_quota import S3QuotaFactory


@pytest.fixture(scope="function")
def s3_quota(account, s3_pool):
    """Create one default S3 quota for given account and pool."""
    quota = S3QuotaFactory.create(
        account_id=account.id,
        pool_id=s3_pool.id,
        default=True,
    )
    yield quota
