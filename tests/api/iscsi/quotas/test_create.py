import pytest
from marshmallow import ValidationError

from app.models.iscsi_quota import IscsiQuotaResponseSchema, IscsiQuotas
from app.models.iscsi_target import IscsiTargets
from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_quota import IscsiQuotaPayload
from tests.schemes.iscsi_quota import IscsiQuotaResponseTestSchema


def validate_response(body):
    try:
        IscsiQuotaResponseTestSchema().load(body)
    except ValidationError as exc:
        pytest.fail(f"iSCSI quota response validation failed: {exc.messages}")


def make_create_quota_payload(env, account, cluster, pool_name="nvme", **overrides):
    return IscsiQuotaPayload.build(
        constrained_limits=True,
        account_name=account.name,
        pool_id=env.iscsi_pools[pool_name].id,
        target={"cluster_name": cluster.name},
        **overrides,
    )


def assert_quota_created(body, account, payload):
    validate_response(body)
    assert body["account"]["id"] == account.id
    assert body["pool"]["id"] == payload["pool_id"]
    assert body["clients"] == payload["clients"]
    assert body["data_size_gb"] == payload["data_size_gb"]
    assert body["disks"] == payload["disks"]
    assert body["snapshots"] == payload["snapshots"]
    assert IscsiQuotas.query.filter_by(id=body["id"]).first() is not None
    assert IscsiTargets.get_target(account.id, payload["pool_id"]) is not None


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_create_iscsi_quota_in_own_account(
    api,
    env,
    role,
):
    """Owner and admin can create iSCSI quota in their own account."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = make_create_quota_payload(env, account, cluster)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    assert_quota_created(body, account, payload)


def test_member_cannot_create_iscsi_quota(api, env):
    """Member has no permission to create iSCSI quotas."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = make_create_quota_payload(env, account, cluster)
    headers = HeadersPayload.build(account=account.name, role="member")

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status == 403


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_create_iscsi_quota_in_other_account(
    api,
    env,
    role,
):
    """Account roles cannot create iSCSI quota for another account."""
    target_account, foreign_account = env.accounts(count=2)
    cluster = env.cluster(account=target_account)
    payload = make_create_quota_payload(env, target_account, cluster)
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status == 404
    assert IscsiQuotas.query.filter_by(
        account_id=target_account.id,
        pool_id=payload["pool_id"],
    ).first() is None


def test_operator_can_create_iscsi_quota_in_any_account(api, env):
    """Operator can create iSCSI quota for any account."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = make_create_quota_payload(env, account, cluster)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    assert_quota_created(body, account, payload)


def test_create_iscsi_quota_rejects_duplicate_pool_quota(api, env):
    """Only one iSCSI quota per account and pool is allowed."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = make_create_quota_payload(env, account, cluster)
    headers = HeadersPayload.build(operator=True)

    first_status, _ = api.iscsi.quotas.create(payload=payload, header=headers)
    second_status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert first_status in (200, 201)
    assert second_status == 409
    assert "already exists" in body["message"]


def test_create_iscsi_quota_rejects_value_over_pool_limit(api, env):
    """iSCSI quota values cannot exceed default pool limitset values."""
    account = env.account()
    cluster = env.cluster(account=account)
    pool = env.iscsi_pools["nvme"]
    limitset = IscsiQuotas.get_pool_limitset(pool.id)
    payload = make_create_quota_payload(
        env,
        account,
        cluster,
        data_size_gb=limitset.data_size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status == 400
    assert "data_size_gb" in str(body)


def test_create_iscsi_quota_response_includes_usage_limits_and_target(
    api,
    env,
):
    """Create response should include empty usage, pool limits, and target state."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = make_create_quota_payload(env, account, cluster)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    validate_response(body)
    assert body["usage"] == {
        "clients": 0,
        "data_size_gb": 0,
        "disks": 0,
        "snapshots": 0,
        "snapshots_size_gb": 0,
    }
    assert body["limits"]["clients"] >= body["clients"]
    assert body["limits"]["data_size_gb"] >= body["data_size_gb"]
    assert body["limits"]["disks"] >= body["disks"]
    assert body["limits"]["snapshots"] >= body["snapshots"]
    assert body["target"]["pool"]["id"] == payload["pool_id"]


def test_iscsi_quota_response_schema_accepts_created_quota(api, env):
    """Response schema should match a freshly created iSCSI quota object."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = make_create_quota_payload(env, account, cluster)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.create(payload=payload, header=headers)

    assert status in (200, 201)
    quota = IscsiQuotas.query.filter_by(id=body["id"]).first()
    IscsiQuotaResponseSchema().dump(quota)
    validate_response(body)
