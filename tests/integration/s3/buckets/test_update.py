import pytest

from app.lib.s3.service import CephService
from tests.factories.bucket import (
    SMALL_BUCKET_QUOTA,
    TYPICAL_BUCKET_QUOTA,
    UNLIMITED_BUCKET_QUOTA,
)
from tests.factories.headers import HeadersPayload


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_update_bucket_quota_is_applied_in_ceph(api, env, pool_name):
    """Bucket quota update is persisted in Ceph for each seeded S3 pool."""
    bucket_ctx = env.bucket_scope(pool_name=pool_name)
    payload = {"quota": TYPICAL_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 200
    assert body["quota"] == payload["quota"]

    bucket = CephService().get_bucket_by_path(bucket_ctx.bucket.path)
    assert bucket.quota == payload["quota"]


def test_update_bucket_unlimited_quota_is_applied_in_ceph(api, env):
    bucket_ctx = env.bucket_scope(bucket_kwargs={"quota": SMALL_BUCKET_QUOTA.copy()})
    payload = {"quota": UNLIMITED_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 200
    assert body["quota"] == UNLIMITED_BUCKET_QUOTA

    bucket = CephService().get_bucket_by_path(bucket_ctx.bucket.path)
    assert bucket.quota == UNLIMITED_BUCKET_QUOTA


def test_partial_bucket_update_preserves_unspecified_quota(api, env):
    """Updating only one bucket quota field preserves the other value."""
    bucket_ctx = env.bucket_scope(
        bucket_kwargs={"quota": {"data_size_mb": 2, "objects": 1}},
    )
    payload = {"quota": {"objects": 2}}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    print(body)
    assert status == 200
    assert body["quota"] == {"data_size_mb": 2, "objects": 2}
    bucket = CephService().get_bucket_by_path(bucket_ctx.bucket.path)
    assert bucket.quota == {"data_size_mb": 2, "objects": 2}
