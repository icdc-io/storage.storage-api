import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_targets import IscsiTargetPayload
from tests.helpers import ensure_list


def ensure_list(obj):
    """Ensures object is a list (wraps single objects)."""
    return obj if isinstance(obj, list) else [obj]


@pytest.mark.parametrize("pool_name", ["nvme", "ssd"])
def test_operator_create_target_returns_204(api, account_factory, cluster_factory, iscsi_pools, pool_name):
    """Operator can create targets (204 No Content)."""
    acc = account_factory()
    cluster = cluster_factory(acc)

    headers = HeadersPayload.build(operator=True)
    pool_id = iscsi_pools[pool_name].id
    payload = IscsiTargetPayload.build(cluster_id=cluster.id, pool_id=pool_id)
    status, body = api.iscsi.targets.create(payload=payload, hdr=headers)

    assert status == 204
    assert body in (None, "", {})
    targets = cluster.to_dict().get("targets", [])
    assert any(t.get("pool").get("id") == pool_id for t in targets)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_roles_cannot_create_target(api, account_factory, cluster_factory, iscsi_pools, role):
    """Only operator can create targets."""
    acc = account_factory()
    cluster = cluster_factory(acc)

    headers = HeadersPayload.build(account=cluster.account.name, role=role)
    payload = IscsiTargetPayload.build(cluster_id=cluster.id, pool_id=iscsi_pools["nvme"].id)
    status, body = api.iscsi.targets.create(payload=payload, hdr=headers)

    assert status == 403
    assert "forbidden" in str(body).lower()


@pytest.mark.parametrize("payload,missing_field", [
    ({"pool_id": 123}, "cluster_id"),
    ({"cluster_id": 456}, "pool_id"),
])
def test_create_target_missing_fields_returns_400(api, account_factory, payload, missing_field):
    """Missing cluster_id or pool_id returns 404/400."""
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.targets.create(payload=payload, hdr=headers)

    assert status == 404
    assert "not found" in str(body).lower()


def test_create_target_with_unknown_cluster_returns_404(api, account_factory, iscsi_pools):
    """Unknown cluster_id should return 404."""
    headers = HeadersPayload.build(operator=True)
    unknown_cluster_id = 999999999
    payload = IscsiTargetPayload.build(cluster_id=unknown_cluster_id, pool_id=iscsi_pools["ssd"].id)
    status, body = api.iscsi.targets.create(payload=payload, hdr=headers)

    assert status in (400, 404)


def test_create_target_with_unknown_pool_returns_404(api, account_factory, cluster_factory):
    """Unknown pool_id should return 404."""
    acc = account_factory()
    cluster = cluster_factory(acc)

    headers = HeadersPayload.build(operator=True)
    unknown_pool_id = 999999999
    payload = IscsiTargetPayload.build(cluster_id=cluster.id, pool_id=unknown_pool_id)
    status, body = api.iscsi.targets.create(payload=payload, hdr=headers)

    assert status in (400, 404)


def test_create_target_unique_pool_per_account_conflict(api, account_factory, cluster_factory, iscsi_pools):
    """Pool must be unique within account (conflict on duplicate)."""
    acc = account_factory()
    clusters = ensure_list(cluster_factory(acc, count=2))

    headers = HeadersPayload.build(operator=True)
    pool_id = iscsi_pools["nvme"].id

    st1, _ = api.iscsi.targets.create(
        payload=IscsiTargetPayload.build(cluster_id=clusters[0].id, pool_id=pool_id),
        hdr=headers,
    )
    assert st1 == 204

    st2, body2 = api.iscsi.targets.create(
        payload=IscsiTargetPayload.build(cluster_id=clusters[1].id, pool_id=pool_id),
        hdr=headers,
    )
    assert st2 in (409, 400)
    assert "exist" in str(body2).lower() or "exists" in str(body2).lower()

    all_targets = [t for c in clusters for t in c.to_dict().get("targets", [])]
    count_same_pool = sum(1 for t in all_targets if t.get("pool").get("id") == pool_id)
    assert count_same_pool == 1


@pytest.mark.parametrize("pool_name", ["nvme"])
def test_create_target_unique_pool_per_cluster_conflict(api, account_factory, cluster_factory, iscsi_pools, pool_name):
    """Pool must be unique within one cluster."""
    acc = account_factory()
    cluster = cluster_factory(acc)

    headers = HeadersPayload.build(operator=True)
    pool_id = iscsi_pools[pool_name].id

    st1, _ = api.iscsi.targets.create(
        payload=IscsiTargetPayload.build(cluster_id=cluster.id, pool_id=pool_id),
        hdr=headers,
    )
    assert st1 == 204

    st2, body2 = api.iscsi.targets.create(
        payload=IscsiTargetPayload.build(cluster_id=cluster.id, pool_id=pool_id),
        hdr=headers,
    )
    assert st2 in (409, 400)
    assert "exist" in str(body2).lower() or "exists" in str(body2).lower()

    targets = cluster.to_dict().get("targets", [])
    assert sum(1 for t in targets if t.get("pool").get("id") == pool_id) == 1
