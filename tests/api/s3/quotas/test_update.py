import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.s3_quota import S3QuotaUpdatePayloadFactory
from tests.schemes.s3_quota import S3QuotaResponseTestSchema


def validate_response(body):
    try:
        S3QuotaResponseTestSchema().load(body)
    except ValidationError as exc:
        pytest.fail(f"S3 quota response validation failed: {exc.messages}")


def make_update_quota_payload(**overrides):
    return S3QuotaUpdatePayloadFactory.build(
        increased_limits=True,
        **overrides,
    )


def assert_quota_updated(body, quota, payload):
    validate_response(body)
    assert body["id"] == quota.id
    assert body["users"] == payload["users"]
    assert body["buckets"] == payload["buckets"]
    assert body["objects"] == payload["objects"]
    assert body["data_size_mb"] == payload["data_size_mb"]


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_update_own_s3_quota(api, env, role):
    """Owner and admin can update S3 quota in their own account."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
        users=10,
        buckets=20,
        objects=30,
        data_size_mb=200,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.s3.quotas.update(quota.id, payload, headers)

    assert status == 200
    assert_quota_updated(body, quota, payload)


def test_member_cannot_update_s3_quota(api, env):
    """Member has no permission to update S3 quotas."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
        users=10,
        buckets=20,
        objects=30,
        data_size_mb=200,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(account=account.name, role="member")

    status, body = api.s3.quotas.update(quota.id, payload, headers)

    assert status == 403


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_update_s3_quota_in_other_account(api, env, role):
    """Owner/admin cannot update S3 quota belonging to another account."""
    quota_account, foreign_account = env.accounts(count=2)
    quota = env.quota(
        account=quota_account,
        pool_name="nvme",
        users=10,
        buckets=20,
        objects=30,
        data_size_mb=200,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.s3.quotas.update(quota.id, payload, headers)

    assert status == 404


def test_operator_can_update_s3_quota_in_any_account(api, env):
    """Operator can update S3 quota in any account."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
        users=10,
        buckets=20,
        objects=30,
        data_size_mb=200,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.update(quota.id, payload, headers)

    assert status == 200
    assert_quota_updated(body, quota, payload)


def test_update_s3_quota_rejects_value_over_pool_limit(api, env):
    """S3 quota update cannot exceed default pool limitset."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
        users=10,
        buckets=20,
        objects=30,
        data_size_mb=200,
    )
    payload = {"data_size_mb": quota.get_limitset().data_size_mb + 1}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.update(quota.id, payload, headers)

    assert status == 400
    assert "data_size_mb" in str(body)


def test_update_s3_quota_rejects_value_below_current_usage(
    api,
    env,
):
    """S3 quota update cannot be lower than current S3 user quota usage."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
        users=10,
        buckets=20,
        objects=30,
        data_size_mb=200,
    )
    env.user(
        account=account,
        pool_name="nvme",
        quota={"buckets": 4, "objects": 5, "data_size_mb": 6},
        usage={"buckets": 0, "objects": 0, "data_size_mb": 0},
    )
    payload = {"buckets": 3}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.update(quota.id, payload, headers)

    assert status == 400
    assert "buckets" in str(body)


def test_update_nonexistent_s3_quota_returns_404(api):
    """Updating a nonexistent S3 quota returns 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.update(999999, {"users": 1}, headers)

    assert status == 404
