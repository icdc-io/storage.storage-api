import pytest
from marshmallow import ValidationError

from app.lib.s3.exceptions import CephServiceException
from app.models.s3_user import S3Users
from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import TYPICAL_USER_QUOTA, S3UserCreatePayloadFactory
from tests.schemes.s3_user import S3UserTestResponseSchema


def assert_valid_s3_user_response(body):
    try:
        S3UserTestResponseSchema().load(body)
    except ValidationError as exc:
        pytest.fail(f"S3 User response schema validation failed: {exc.messages}")


def make_create_payload(scope_ctx, **overrides):
    payload = S3UserCreatePayloadFactory.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
        typical_quota=True,
    )
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_can_create_s3_user_in_own_account(
    api,
    env,
    role,
):
    """Owner, admin, and member can create an S3 user in their own account."""
    scope_ctx = env.scope(pool_name="nvme")
    payload = make_create_payload(scope_ctx)
    headers = HeadersPayload.build(account=scope_ctx.account.name, role=role)

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 201
    assert_valid_s3_user_response(body)
    assert body["account"]["name"] == scope_ctx.account.name
    assert body["pool"]["id"] == scope_ctx.quota.pool_id
    assert body["name"] == f"{scope_ctx.account.name}${payload['name']}"
    assert body["quota"] == payload["quota"]
    assert S3Users.query.filter_by(id=body["id"]).one().name == body["name"]


def test_operator_can_create_s3_user_in_any_account(
    api,
    env,
):
    """Operator can create an S3 user for another account using the devel account."""
    scope_ctx = env.scope(pool_name="nvme")
    payload = make_create_payload(scope_ctx)
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 201
    assert_valid_s3_user_response(body)
    assert body["account"]["name"] == scope_ctx.account.name
    assert body["name"] == f"{scope_ctx.account.name}${payload['name']}"


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_cannot_create_s3_user_in_foreign_account(
    api,
    env,
    role,
):
    own_account, foreign_account = env.accounts(count=2)
    env.scope(account=own_account)
    foreign_scope = env.scope(account=foreign_account)

    payload = make_create_payload(foreign_scope)
    headers = HeadersPayload.build(account=own_account.name, role=role)

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 404
    assert "Account with this name not found" in body["message"]


def test_create_s3_user_uses_subject_account_when_payload_has_no_account_name(
    api,
    env,
):
    scope_ctx = env.scope()
    payload = make_create_payload(scope_ctx, account_name=None)
    headers = HeadersPayload.build(account=scope_ctx.account.name, role="member")

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 201
    assert_valid_s3_user_response(body)
    assert body["account"]["name"] == scope_ctx.account.name
    assert body["name"] == f"{scope_ctx.account.name}${payload['name']}"


def test_create_s3_user_returns_404_when_account_does_not_exist(api, env):
    scope_ctx = env.scope()
    payload = make_create_payload(scope_ctx, account_name="missing-account")
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 404
    assert "Account with this name not found" in body["message"]


def test_create_s3_user_returns_404_when_pool_does_not_exist(api, env):
    scope_ctx = env.scope()
    payload = make_create_payload(scope_ctx, pool_id=999999)
    headers = HeadersPayload.build(account=scope_ctx.account.name, role="owner")

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 404
    assert "Pool with this ID not found" in body["message"]


def test_create_s3_user_returns_404_when_account_quota_does_not_exist(api, env):
    account = env.account()
    payload = S3UserCreatePayloadFactory.build(
        account_name=account.name,
        pool_id=env.s3_pools["nvme"].id,
        typical_quota=True,
    )
    headers = HeadersPayload.build(account=account.name, role="owner")

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 404
    assert "Account quota not found" in body["message"]


def test_create_s3_user_returns_400_when_payload_is_invalid(api, env):
    scope_ctx = env.scope()
    payload = make_create_payload(scope_ctx, owner="not-email")
    headers = HeadersPayload.build(account=scope_ctx.account.name, role="owner")

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 400
    assert body["message"] == "Invalid parameters"
    assert any("owner:" in error for error in body["errors"])


def test_create_s3_user_returns_400_when_quota_overflows_account(api, env):
    scope_ctx = env.scope(data_size_mb=5, objects=5, buckets=1, users=10)
    payload = make_create_payload(scope_ctx, quota=TYPICAL_USER_QUOTA.copy())
    headers = HeadersPayload.build(account=scope_ctx.account.name, role="owner")

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 400
    assert body["message"] == "Invalid parameters"
    assert (
        "data_size_mb: Overflow of account quota on data_size_mb: 10/5"
        in body["errors"]
    )


def test_create_s3_user_returns_400_when_ceph_create_fails(
    api,
    env,
    fake_s3_ceph,
):
    scope_ctx = env.scope()
    fake_s3_ceph.create_user_error = CephServiceException("ceph create failed", code=400)
    payload = make_create_payload(scope_ctx)
    headers = HeadersPayload.build(account=scope_ctx.account.name, role="owner")

    status, body = api.s3.users.create(payload=payload, header=headers)

    assert status == 400
    assert (
        body["message"] == f"Failed to create S3 user {scope_ctx.account.name}${payload['name']}"
    )
    assert body["errors"] == ["ceph create failed"]
