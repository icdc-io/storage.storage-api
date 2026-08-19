import pytest

from app.lib.s3.service import CephService
from app.models.s3_user import S3UserStatus
from tests.builders.s3_operations import S3Operations
from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import (
    ACTIVE_USER_QUOTA,
    TYPICAL_USER_QUOTA,
    S3UserUpdatePayloadFactory,
)
from tests.schemes.s3_user import S3UserTestResponseSchema
from tests.support.assertions import assert_schema_response


def update_s3_user(api, s3_user, payload):
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.update(s3_user.id, payload, headers)

    assert status == 200
    assert_schema_response(body, S3UserTestResponseSchema)

    CephService().enrich(s3_user)
    return body, s3_user


def lock_s3_user_in_ceph(s3_user):
    service = CephService()
    service.update_s3_user(s3_user=s3_user, status=S3UserStatus.LOCKED)
    service.enrich(s3_user)
    assert s3_user.status == S3UserStatus.LOCKED
    return s3_user


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_update_user_quota_is_applied_in_ceph(api, env, pool_name):
    user_ctx = env.user_scope(
        pool_name=pool_name,
        user_quota=ACTIVE_USER_QUOTA.copy(),
    )
    payload = S3UserUpdatePayloadFactory.build(quota=TYPICAL_USER_QUOTA.copy())

    body, s3_user = update_s3_user(api, user_ctx.user, payload)

    assert body["quota"] == TYPICAL_USER_QUOTA
    assert s3_user.quota == TYPICAL_USER_QUOTA


def test_update_locked_user_quota_is_applied_in_ceph(api, env):
    user_ctx = env.user_scope(user_quota=ACTIVE_USER_QUOTA.copy())
    lock_s3_user_in_ceph(user_ctx.user)
    payload = S3UserUpdatePayloadFactory.build(quota=TYPICAL_USER_QUOTA.copy())

    body, s3_user = update_s3_user(api, user_ctx.user, payload)

    assert body["status"] == S3UserStatus.LOCKED
    assert body["quota"] == TYPICAL_USER_QUOTA
    assert s3_user.status == S3UserStatus.LOCKED
    assert s3_user.quota == TYPICAL_USER_QUOTA


def test_lock_user_in_ceph(api, env):
    user_ctx = env.user_scope()
    payload = S3UserUpdatePayloadFactory.build(status=S3UserStatus.LOCKED.value)

    body, s3_user = update_s3_user(api, user_ctx.user, payload)

    assert body["status"] == S3UserStatus.LOCKED
    assert s3_user.status == S3UserStatus.LOCKED


def test_unlock_user_in_ceph(api, env):
    user_ctx = env.user_scope()
    lock_s3_user_in_ceph(user_ctx.user)
    payload = S3UserUpdatePayloadFactory.build(status=S3UserStatus.ACTIVE.value)

    body, s3_user = update_s3_user(api, user_ctx.user, payload)

    assert body["status"] == S3UserStatus.ACTIVE
    assert s3_user.status == S3UserStatus.ACTIVE


def test_update_user_owner_or_display_name_in_ceph(api, env):
    user_ctx = env.user_scope(owner="old-owner@example.com")
    payload = S3UserUpdatePayloadFactory.build(owner="new-owner@example.com")

    body, s3_user = update_s3_user(api, user_ctx.user, payload)

    metadata = CephService().admin.get_user_info(s3_user.name)

    assert body["owner"] == payload["owner"]
    assert s3_user.owner == payload["owner"]
    assert metadata["display_name"] == payload["owner"]


def test_update_deleted_user_is_not_applied(api, env):
    user_ctx = env.user_scope()
    headers = HeadersPayload.build(operator=True)

    S3Operations.delete_user(user_ctx.user)

    payload = S3UserUpdatePayloadFactory.build(owner="deleted-owner@example.com")
    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 404
    assert body["message"] == "S3 User not found or you haven't access for it."
    assert CephService().admin.get_user_info(user_ctx.user.name) == {}
