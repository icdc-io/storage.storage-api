import pytest

from tests.factories.headers import HeadersPayload
from tests.helpers import ensure_list
from tests.iscsi.clusters.conftest import validate_response


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
@pytest.mark.parametrize("n_clusters", [1, 2, 5])
def test_non_operator_lists_exact_own_clusters_no_query(api, account_factory, cluster_factory, role, n_clusters):
    """Non-operator roles see only their own clusters."""
    accounts = account_factory(count=2)
    own, other = accounts[0], accounts[1]
    own_clusters = ensure_list(cluster_factory(own, count=n_clusters))
    cluster_factory(other, count=3)

    headers = HeadersPayload.build(account=own.name, role=role)
    status, body = api.iscsi.clusters.list(hdr=headers)

    assert status == 200
    validate_response(body)
    got_ids = {c["id"] for c in body}
    assert got_ids == {c.id for c in own_clusters}
    assert all(c["account"]["id"] == own.id for c in body)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_ignores_foreign_account_id_filter(api, account_factory, cluster_factory, role):
    """Foreign account filter should be ignored for non-operators."""
    accounts = account_factory(count=2)
    own, other = accounts[0], accounts[1]
    own_clusters = ensure_list(cluster_factory(own, count=2))
    cluster_factory(other, count=4)

    headers = HeadersPayload.build(account=own.name, role=role, user=f"{own.name}@ex.com")
    status, body = api.iscsi.clusters.list(query={"account_id": other.id}, hdr=headers)

    assert status == 200
    validate_response(body)
    got_ids = {c["id"] for c in body}
    assert got_ids == {c.id for c in own_clusters}


@pytest.mark.parametrize("n_clusters", [1, 3])
def test_operator_filter_by_account_id_exact_set(api, account_factory, cluster_factory, n_clusters):
    """Operator filters clusters by account_id correctly."""
    accounts = account_factory(count=3)
    acc0, target, acc2 = accounts[0], accounts[1], accounts[2]
    target_clusters = ensure_list(cluster_factory(target, count=n_clusters))
    cluster_factory(acc0, count=2)
    cluster_factory(acc2, count=4)

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.list(query={"account_id": target.id}, hdr=headers)

    assert status == 200
    validate_response(body)
    got_ids = {c["id"] for c in body}
    assert got_ids == {c.id for c in target_clusters}
    assert all(c["account"]["id"] == target.id for c in body)


def test_operator_filter_by_cluster_name_exact(api, account_factory, cluster_factory):
    """Operator filters clusters by exact name."""
    acc = account_factory()
    clusters = ensure_list(cluster_factory(acc, count=3))
    pick = clusters[1]

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.list(query={"name": pick.name}, hdr=headers)

    assert status == 200
    validate_response(body)
    got_ids = {c["id"] for c in body}
    assert got_ids == {pick.id}


def test_operator_filter_by_cluster_name_no_match_returns_empty(api, account_factory, cluster_factory):
    """Filtering by missing name returns empty list."""
    acc = account_factory()
    cluster_factory(acc, count=2)

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.list(query={"name": "cluster-deadbeef"}, hdr=headers)

    assert status == 200
    validate_response(body)
    assert body == []


def test_operator_filter_by_account_name(api, account_factory, cluster_factory):
    """Operator filters clusters by account name."""
    accounts = account_factory(count=3)
    a0, a1, a2 = accounts[0], accounts[1], accounts[2]
    cluster_factory(a0, count=1)
    target_clusters = ensure_list(cluster_factory(a1, count=2))
    cluster_factory(a2, count=3)

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.list(query={"accounts.name": a1.name}, hdr=headers)

    assert status == 200
    validate_response(body)
    got_ids = {c["id"] for c in body}
    assert got_ids == {c.id for c in target_clusters}


def test_operator_filter_by_account_id_and_name(api, account_factory, cluster_factory):
    """Operator filters by both account_id and name."""
    accounts = account_factory(count=2)
    a0, a1 = accounts[0], accounts[1]
    a0_clusters = ensure_list(cluster_factory(a0, count=3))
    pick = a0_clusters[0]
    cluster_factory(a1, count=2)

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.list(query={"account_id": a0.id, "name": pick.name}, hdr=headers)

    assert status == 200
    validate_response(body)
    assert len(body) == 1
    assert body[0]["id"] == pick.id
    assert body[0]["account"]["id"] == a0.id


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_filter_by_own_cluster_name(api, account_factory, cluster_factory, role):
    """Non-operator filters only own cluster by name."""
    acc = account_factory()
    clusters = ensure_list(cluster_factory(acc, count=3))
    pick = clusters[2]

    headers = HeadersPayload.build(account=acc.name, role=role)
    status, body = api.iscsi.clusters.list(query={"name": pick.name}, hdr=headers)

    assert status == 200
    validate_response(body)
    assert len(body) == 1
    assert body[0]["id"] == pick.id


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_filter_by_foreign_account_name_is_ignored(api, account_factory, cluster_factory, role):
    """Foreign account name should be ignored for non-operators."""
    accounts = account_factory(count=2)
    own, other = accounts[0], accounts[1]
    cluster_factory(own, count=2)
    other_clusters = ensure_list(cluster_factory(other, count=3))

    headers = HeadersPayload.build(account=own.name, role=role)
    status, body = api.iscsi.clusters.list(query={"name": other_clusters[0].name}, hdr=headers)

    assert status == 200
    validate_response(body)
    assert body == []


@pytest.mark.parametrize("layout", [
    [{"pools": ["nvme"], "gateways": 2}],
    [{"pools": ["nvme", "ssd"], "gateways": 2},
     {"pools": ["ssd"], "gateways": 1},
     {"pools": [], "gateways": 0}],
])
def test_operator_filter_by_account_with_children_layout(
    api, account_factory, cluster_factory, target_factory, gateway_factory, layout
):
    """Operator gets clusters with proper child relations."""
    accounts = account_factory(count=3)
    acc0, target, acc2 = accounts[0], accounts[1], accounts[2]
    cluster_factory(acc0, count=2)
    cluster_factory(acc2, count=1)
    target_clusters = ensure_list(cluster_factory(target, count=len(layout)))

    for cl, spec in zip(target_clusters, layout):
        if spec["pools"]:
            target_factory(cl, target_pools=spec["pools"])
        if spec["gateways"]:
            gateway_factory(cl, count=spec["gateways"])

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.list(query={"account_id": target.id}, hdr=headers)

    assert status == 200
    validate_response(body)
    got_ids = {c["id"] for c in body}
    assert got_ids == {c.id for c in target_clusters}

    by_id = {c["id"]: c for c in body}
    for idx, cl in enumerate(target_clusters):
        item = by_id[cl.id]
        assert len(item["gateways"]) == layout[idx]["gateways"]
        assert len(item["targets"]) == len(layout[idx]["pools"])


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_filter_own_by_name_with_children(api, account_factory, cluster_factory, target_factory, gateway_factory, role):
    """Non-operator filters own cluster including children."""
    acc = account_factory()
    clusters = ensure_list(cluster_factory(acc, count=3))
    pick = clusters[1]
    target_factory(pick, target_pools=["nvme", "ssd"])
    gateway_factory(pick, count=2)

    headers = HeadersPayload.build(account=acc.name, role=role)
    status, body = api.iscsi.clusters.list(query={"name": pick.name}, hdr=headers)

    assert status == 200
    validate_response(body)
    assert len(body) == 1

    item = body[0]
    assert item["id"] == pick.id
    assert len(item["gateways"]) == 2
