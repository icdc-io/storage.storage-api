import pytest
from sqlalchemy import delete

from tests.factory.s3_quota import S3QuotaFactory


@pytest.fixture(scope="package")
def seed_s3_quota(aqa_acc, s3_ssd):
    S3QuotaFactory.create(account_id=aqa_acc.id,
                          pool_id=s3_ssd.id,
                          users=5,
                          buckets=10,
                          objects=20,
                          data_size_mb=100
                          )

    yield


@pytest.fixture
def clean_up_s3_quota(ceph_cleanup_registry):
    from app.database import db
    from app.models.s3_quota import S3Quotas

    def register(quota_id: int, delete_db: bool = True):
        if delete_db:
            ceph_cleanup_registry.append(
                lambda quota_id=quota_id: (
                    db.session.execute(delete(S3Quotas).where(S3Quotas.id == quota_id)),
                    db.session.flush(),
                )
            )

    return register


@pytest.fixture(scope="function")
def s3_quota(headers_factory, aqa_acc, s3_ssd, seed_account):
    quota = S3QuotaFactory.create(account_id=aqa_acc.id,
                          pool_id=s3_ssd.id,
                          users=5,
                          buckets=10,
                          objects=20,
                          data_size_mb=100
                          )
    yield quota
