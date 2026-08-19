import pytest
from marshmallow import ValidationError

from app.models.s3_quota import S3Quotas
from tests.factories.headers import HeadersPayload
from tests.factories.s3_quota import S3QuotaPayloadFactory
from tests.schemes.s3_quota import S3QuotaResponseTestSchema


def validate_response(body):
    try:
        S3QuotaResponseTestSchema().load(body)
    except ValidationError as exc:
        pytest.fail(f"S3 quota response validation failed: {exc.messages}")


def make_create_quota_payload(account, pool, **overrides):
    defaults = {
        "account_name": account.name,
        "pool_id": pool.id,
    }
    defaults.update(overrides)
    return S3QuotaPayloadFactory.build(
        constrained_limits=True,
        **defaults,
    )


def assert_quota_created(body, account, payload):
    validate_response(body)
    assert body["account"]["id"] == account.id
    assert body["pool"]["id"] == payload["pool_id"]
    assert body["users"] == payload["users"]
    assert body["buckets"] == payload["buckets"]
    assert body["objects"] == payload["objects"]
    assert body["data_size_mb"] == payload["data_size_mb"]
    assert S3Quotas.query.filter_by(id=body["id"]).first() is not None


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_create_s3_quota_in_own_account(api, env, s3_pools, role):
    """Owner and admin can create S3 quota in their own account."""
    account = env.account()
    payload = make_create_quota_payload(account, s3_pools["nvme"])
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    assert_quota_created(body, account, payload)


def test_member_cannot_create_s3_quota(api, env, s3_pools):
    """Member has no permission to create S3 quotas."""
    account = env.account()
    payload = make_create_quota_payload(account, s3_pools["nvme"])
    headers = HeadersPayload.build(account=account.name, role="member")

    status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert status == 403


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_create_s3_quota_in_other_account(api, env, s3_pools, role):
    """Account roles cannot create S3 quota for another account."""
    target_account, foreign_account = env.accounts(count=2)
    payload = make_create_quota_payload(target_account, s3_pools["nvme"])
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert status == 404
    assert S3Quotas.query.filter_by(
        account_id=target_account.id,
        pool_id=payload["pool_id"],
    ).first() is None


def test_operator_can_create_s3_quota_in_any_account(api, env, s3_pools):
    """Operator can create S3 quota for any account."""
    account = env.account()
    payload = make_create_quota_payload(account, s3_pools["nvme"])
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    assert_quota_created(body, account, payload)


def test_create_s3_quota_rejects_duplicate_pool_quota(api, env, s3_pools):
    """Only one S3 quota per account and pool is allowed."""
    account = env.account()
    payload = make_create_quota_payload(account, s3_pools["nvme"])
    headers = HeadersPayload.build(operator=True)

    first_status, _ = api.s3.quotas.create(payload=payload, header=headers)
    second_status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert first_status in (200, 201)
    assert second_status == 409
    assert "one account quota" in body["message"]


def test_create_s3_quota_rejects_value_over_pool_limit(api, env, s3_pools):
    """S3 quota values cannot exceed default pool limitset values."""
    account = env.account()
    pool = s3_pools["nvme"]
    limitset = S3Quotas.get_pool_limitset(pool.id)
    payload = make_create_quota_payload(
        account,
        pool,
        data_size_mb=limitset.data_size_mb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert status == 400
    assert "data_size_mb" in str(body)


def test_create_s3_quota_response_includes_usage_limits_and_endpoints(api, env, s3_pools):
    """Create response should include empty usage, pool limits, and S3 endpoints."""
    account = env.account()
    payload = make_create_quota_payload(account, s3_pools["nvme"])
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    validate_response(body)
    assert body["usage"] == {
        "users": 0,
        "buckets": 0,
        "objects": 0,
        "data_size_mb": 0,
    }
    assert body["limits"]["users"] >= body["users"]
    assert body["limits"]["buckets"] >= body["buckets"]
    assert body["limits"]["objects"] >= body["objects"]
    assert body["limits"]["data_size_mb"] >= body["data_size_mb"]
    assert set(body["endpoints"]) == {"public", "private"}
