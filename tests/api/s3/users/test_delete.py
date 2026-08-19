import pytest

from app.models.s3_user import S3Users
from tests.factories.headers import HeadersPayload


def assert_s3_user_deleted(s3_user):
    assert S3Users.query.filter_by(id=s3_user.id).first() is None


def assert_s3_user_exists(s3_user):
    assert S3Users.query.filter_by(id=s3_user.id).first() is not None


def test_member_can_delete_own_s3_user(api, env):
    """Member can delete their own S3 user."""
    user_ctx = env.user_scope(pool_name="nvme")
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user=user_ctx.user.owner,
    )

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 204
    assert_s3_user_deleted(user_ctx.user)


def test_member_cannot_delete_non_own_s3_user(api, env):
    """Member cannot delete an S3 user owned by another user."""
    user_ctx = env.user_scope(pool_name="nvme")
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user="other_user@example.com",
    )

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 404
    assert_s3_user_exists(user_ctx.user)


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_delete_account_s3_user(api, env, role):
    """Admin and owner can delete S3 users in their own account."""
    user_ctx = env.user_scope(pool_name="nvme")
    headers = HeadersPayload.build(account=user_ctx.account.name, role=role)

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 204
    assert_s3_user_deleted(user_ctx.user)


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_delete_s3_user_in_other_account(api, env, role):
    """Non-operator roles cannot delete an S3 user in another account."""
    user_ctx = env.user_scope(pool_name="nvme")
    foreign_account = env.account()
    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=user_ctx.user.owner,
    )

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 404
    assert_s3_user_exists(user_ctx.user)


def test_operator_can_delete_s3_user_in_any_account(api, env):
    """Operator can delete an S3 user in any account."""
    user_ctx = env.user_scope(pool_name="nvme")
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 204
    assert_s3_user_deleted(user_ctx.user)


def test_delete_nonexistent_s3_user_returns_404(api):
    """Deleting a nonexistent S3 user returns 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.delete(99999, headers)

    assert status == 404
