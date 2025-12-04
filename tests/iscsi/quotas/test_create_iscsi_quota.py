import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_quota import IscsiQuotaPayload


@pytest.mark.parametrize("body", [
    {"data_size_gb": 49, "snapshots": 22, "clients": 14, "disks": 22},
    {"data_size_gb": 1, "snapshots": 1, "clients": 1, "disks": 1},
    {"data_size_gb": 22, "snapshots": 16, "clients": 11, "disks": 4},
])
def test_operator_can_create_for_any_account(api, account_factory, iscsi_pools, body):
    """Operator can create quotas for any account and pool."""
    acc = account_factory()
    hdr = HeadersPayload.build(operator=True)

    for pool in iscsi_pools.values():
        payload = IscsiQuotaPayload.build(account_name=acc.name, pool_id=pool.id, **body)
        st, _ = api.iscsi.quotas.create(payload=payload, hdr=hdr)
        assert st in (200, 201), f"Failed for pool={pool.name}"


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_create_in_own_account(api, account_factory, iscsi_pool, role):
    """Owner/Admin can create quotas only in their own account."""
    acc = account_factory()
    hdr = HeadersPayload.build(account=acc.name, role=role)
    payload = IscsiQuotaPayload.build(default=True, account_name=acc.name, pool_id=iscsi_pool.id)
    st, _ = api.iscsi.quotas.create(payload=payload, hdr=hdr)
    assert st in (200, 201)


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_create_in_other_account(api, account_factory, iscsi_pool, role):
    """Owner/Admin cannot create quotas for another account."""
    accounts = account_factory(count=2)
    actor, target = accounts[0], accounts[1]
    hdr = HeadersPayload.build(account=actor.name, role=role)
    payload = IscsiQuotaPayload.build(account_name=target.name, pool_id=iscsi_pool.id)
    st, body = api.iscsi.quotas.create(payload=payload, hdr=hdr)
    assert st == 404
    assert "permission" in str(body).lower()


def test_member_cannot_create_quota(api, account_factory, iscsi_pool):
    """Member role cannot create quotas."""
    acc = account_factory()
    hdr = HeadersPayload.build(account=acc.name, role="member")
    payload = IscsiQuotaPayload.build(account_name=acc.name, pool_id=iscsi_pool.id)
    st, body = api.iscsi.quotas.create(payload=payload, hdr=hdr)
    assert st == 403
    assert "forbidden" in str(body).lower()


@pytest.mark.parametrize("field", ["data_size_gb", "snapshots", "clients", "disks"])
def test_exceed_limit_returns_400_or_409(api, account_factory, iscsi_pool, get_pool_limitset, field):
    """Exceeding quota limit returns 400 or 409."""
    acc = account_factory()
    hdr = HeadersPayload.build(operator=True)
    limits = get_pool_limitset(iscsi_pool.id)
    limit_val = getattr(limits, field)
    payload = IscsiQuotaPayload.build(
        default=True,
        account_name=acc.name,
        pool_id=iscsi_pool.id,
        **{field: limit_val + 1},
    )
    st, body = api.iscsi.quotas.create(payload=payload, hdr=hdr)
    assert st in (400, 409)
    assert "limit" in str(body).lower() or field in str(body).lower()


def test_unique_per_account_pool_conflict(api, account_factory, iscsi_pool):
    """Each (account, pool) pair must have a single quota."""
    acc = account_factory()
    hdr = HeadersPayload.build(operator=True)
    payload = IscsiQuotaPayload.build(account_name=acc.name, pool_id=iscsi_pool.id, default=True)
    st1, _ = api.iscsi.quotas.create(payload=payload, hdr=hdr)
    assert st1 in (200, 201)
    st2, body2 = api.iscsi.quotas.create(payload=payload, hdr=hdr)
    assert st2 in (409, 400)
    assert "unique" in str(body2).lower() or "exists" in str(body2).lower()
