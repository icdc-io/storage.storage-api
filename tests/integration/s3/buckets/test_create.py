import pytest

from app.lib.s3.service import CephService
from tests.factories.bucket import (
    SMALL_BUCKET_QUOTA,
    UNLIMITED_BUCKET_QUOTA,
    BucketCreatePayloadFactory,
)
from tests.factories.headers import HeadersPayload


def create_bucket(api, env, *, pool_name="nvme", quota=None):
    user_ctx = env.user_scope(pool_name=pool_name)
    payload = BucketCreatePayloadFactory.build(
        user_name=user_ctx.user.name,
        quota=quota or SMALL_BUCKET_QUOTA.copy(),
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 201
    env.track_bucket(CephService().get_bucket_by_path(body["path"]))
    return user_ctx, payload, body


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_create_bucket_for_user_in_ceph(api, env, pool_name):
    user_ctx, payload, body = create_bucket(api, env, pool_name=pool_name)

    bucket = CephService().get_bucket_by_path(body["path"])

    assert body["name"] == payload["name"]
    assert body["user_name"] == user_ctx.user.name
    assert bucket.path == body["path"]
    assert bucket.user_name == user_ctx.user.name
    assert user_ctx.pool_name == pool_name


def test_create_bucket_applies_quota_in_ceph(api, env):
    _, payload, body = create_bucket(
        api,
        env,
        quota=SMALL_BUCKET_QUOTA.copy(),
    )

    bucket = CephService().get_bucket_by_path(body["path"])

    assert body["quota"] == payload["quota"]
    assert bucket.quota == payload["quota"]


def test_create_bucket_applies_unlimited_quota_in_ceph(api, env):
    _, payload, body = create_bucket(
        api,
        env,
        quota=UNLIMITED_BUCKET_QUOTA.copy(),
    )

    bucket = CephService().get_bucket_by_path(body["path"])

    assert body["quota"] == payload["quota"]
    assert bucket.quota == payload["quota"]
