import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import ACTIVE_USER_QUOTA, S3UserUpdatePayloadFactory
from tests.schemes.s3_user import S3UserTestResponseSchema
from tests.support.assertions import assert_schema_response


def assert_valid_s3_user_response(body):
    assert_schema_response(
        body,
        S3UserTestResponseSchema,
        message="S3 User validation failed",
    )


# Permission checks


def test_member_can_update_own_s3_user_without_changing_owner(api, env):
    user_ctx = env.user_scope(owner="member-s3-owner@example.com")
    payload = S3UserUpdatePayloadFactory.build(description="member update")
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user=user_ctx.user.owner,
    )

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 200
    assert_valid_s3_user_response(body)
    assert body["description"] == payload["description"]
    assert body["owner"] == user_ctx.user.owner


def test_member_cannot_transfer_own_s3_user_owner(api, env):
    user_ctx = env.user_scope(owner="member-s3-owner@example.com")
    payload = S3UserUpdatePayloadFactory.build(owner="new-member-owner@example.com")
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user=user_ctx.user.owner,
    )

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 200
    assert_valid_s3_user_response(body)
    assert body["owner"] == user_ctx.user.owner


def test_member_cannot_update_s3_user_with_different_owner(api, env):
    user_ctx = env.user_scope(owner="other-member-owner@example.com")
    payload = S3UserUpdatePayloadFactory.build(description="member hidden update")
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user="requesting-member@example.com",
    )

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 404
    assert body["message"] == "S3 User not found or you haven't access for it."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_update_account_s3_user(api, env, role):
    user_ctx = env.user_scope(owner="account-s3-owner@example.com")
    payload = S3UserUpdatePayloadFactory.build(description=f"{role} update")
    headers = HeadersPayload.build(account=user_ctx.account.name, role=role)

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 200
    assert_valid_s3_user_response(body)
    assert body["description"] == payload["description"]


@pytest.mark.parametrize("role", ["admin", "owner", "member"])
def test_non_operator_roles_cannot_update_foreign_account_s3_user(api, env, role):
    own_account, foreign_account = env.accounts(count=2)
    user_ctx = env.user_scope(account=foreign_account)
    payload = S3UserUpdatePayloadFactory.build(description="foreign update")
    headers = HeadersPayload.build(
        account=own_account.name,
        role=role,
        user=user_ctx.user.owner,
    )

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 404
    assert body["message"] == "S3 User not found or you haven't access for it."


def test_operator_can_update_s3_user_in_any_account(api, env):
    account = env.account()
    user_ctx = env.user_scope(account=account)
    payload = S3UserUpdatePayloadFactory.build(description="operator update")
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 200
    assert_valid_s3_user_response(body)
    assert body["description"] == payload["description"]


# Payload combinations


@pytest.mark.parametrize(
    "payload",
    [
        S3UserUpdatePayloadFactory.build(description="updated by pytest"),
        S3UserUpdatePayloadFactory.build(
            owner="combo-owner@example.com",
            description="combo description",
        ),
        S3UserUpdatePayloadFactory.build(quota=ACTIVE_USER_QUOTA.copy()),
        S3UserUpdatePayloadFactory.build(
            owner="quota-owner@example.com",
            quota=ACTIVE_USER_QUOTA.copy(),
        ),
        S3UserUpdatePayloadFactory.build(
            description="quota description",
            quota=ACTIVE_USER_QUOTA.copy(),
        ),
        S3UserUpdatePayloadFactory.build(
            owner="full-combo-owner@example.com",
            description="full combo description",
            quota=ACTIVE_USER_QUOTA.copy(),
        ),
    ],
    ids=[
        "description",
        "owner-description",
        "quota",
        "owner-quota",
        "description-quota",
        "owner-description-quota",
    ],
)
def test_operator_can_update_valid_s3_user_payload_combinations(api, env, payload):
    user_ctx = env.user_scope()
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 200
    assert_valid_s3_user_response(body)
    for key, value in payload.items():
        if key in {"owner", "description", "quota"}:
            assert body[key] == value


def test_update_s3_user_returns_400_for_invalid_payload(api, env):
    user_ctx = env.user_scope()
    payload = S3UserUpdatePayloadFactory.build(owner="not-email")
    headers = HeadersPayload.build(account=user_ctx.account.name, role="owner")

    status, body = api.s3.users.update(user_ctx.user.id, payload, headers)

    assert status == 400
    assert body["message"] == "Invalid parameters"
    assert any("owner:" in error for error in body["errors"])
