import pytest

from app.lib.s3.service import CephService
from app.models.s3_user import S3Users, S3UserStatus
from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import (
    ACTIVE_USER_QUOTA,
    TYPICAL_USER_QUOTA,
    S3UserCreatePayloadFactory,
)
from tests.schemes.s3_user import S3UserTestResponseSchema
from tests.support.assertions import assert_schema_response


def create_s3_user(api, env, *, pool_name="nvme", name=None, quota=None):
    scope = env.scope(pool_name=pool_name)
    payload = S3UserCreatePayloadFactory.build(
        account_name=scope.account.name,
        pool_id=scope.quota.pool_id,
        quota=quota or ACTIVE_USER_QUOTA.copy(),
    )
    if name is not None:
        payload["name"] = name
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 201
    assert_schema_response(body, S3UserTestResponseSchema)

    created_user = S3Users.query.filter_by(id=body["id"]).first()
    assert created_user is not None
    env.track_user(created_user)

    CephService().enrich(created_user)
    return scope, payload, body, created_user


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_create_user_in_each_pool(api, env, pool_name):
    scope, payload, body, created_user = create_s3_user(
        api,
        env,
        pool_name=pool_name,
    )

    assert body["pool"]["id"] == scope.quota.pool_id
    assert body["name"] == f"{scope.account.name}${payload['name']}"
    assert created_user.pool_id == scope.quota.pool_id
    assert created_user.name == body["name"]


def test_create_user_applies_quota_in_ceph(api, env):
    _, _, body, created_user = create_s3_user(
        api,
        env,
        quota=TYPICAL_USER_QUOTA.copy(),
    )

    assert body["quota"] == TYPICAL_USER_QUOTA
    assert created_user.quota == TYPICAL_USER_QUOTA


def test_create_user_returns_keys_and_active_status(api, env):
    _, _, body, created_user = create_s3_user(api, env)

    assert body["status"] == S3UserStatus.ACTIVE
    assert created_user.status == S3UserStatus.ACTIVE
    assert body["keys"]["s3"]["user"] == created_user.name
    assert body["keys"]["s3"]["access_key"]
    assert body["keys"]["s3"]["secret_key"]
    assert body["keys"]["swift"]["user"] == f"{created_user.name}:swift"
    assert body["keys"]["swift"]["secret_key"]


def test_create_duplicate_user_fails_in_ceph(api, env):
    scope, payload, _, created_user = create_s3_user(api, env)
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert created_user.name == f"{scope.account.name}${payload['name']}"
    assert status == 400
    assert body["message"] == f"Failed to create S3 user {created_user.name}"
