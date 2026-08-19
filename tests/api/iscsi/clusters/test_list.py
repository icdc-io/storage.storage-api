import pytest

from tests.api.iscsi.clusters.conftest import validate_response
from tests.factories.headers import HeadersPayload


def list_clusters(api, headers, query=None):
    status_code, response_body = api.iscsi.clusters.list(query=query, header=headers)

    assert status_code == 200
    validate_response(response_body)
    return response_body


def assert_cluster_ids(response_body, clusters):
    assert {item["id"] for item in response_body} == {cluster.id for cluster in clusters}


def assert_clusters_belong_to_account(response_body, account):
    assert all(item["account"]["id"] == account.id for item in response_body)


def assert_exact_clusters(response_body, clusters, account=None):
    assert_cluster_ids(response_body, clusters)
    if account is not None:
        assert_clusters_belong_to_account(response_body, account)


def assert_single_cluster(response_body, cluster):
    assert len(response_body) == 1
    assert response_body[0]["id"] == cluster.id


def assert_cluster_children_layout(response_body, clusters, children_layout):
    cluster_items_by_id = {item["id"]: item for item in response_body}
    for cluster, expected_children in zip(clusters, children_layout):
        cluster_item = cluster_items_by_id[cluster.id]
        assert len(cluster_item["gateways"]) == expected_children["gateway_count"]
        assert len(cluster_item["targets"]) == len(
            expected_children["target_pool_names"]
        )


def create_cluster_children(env, clusters, children_layout):
    for cluster, expected_children in zip(clusters, children_layout):
        target_pool_names = expected_children["target_pool_names"]
        gateway_count = expected_children["gateway_count"]

        if target_pool_names:
            env.targets(cluster=cluster, pool_names=target_pool_names)
        if gateway_count:
            env.gateways(cluster=cluster, count=gateway_count)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
@pytest.mark.parametrize("n_clusters", [1, 2, 5])
def test_non_operator_lists_only_own_clusters(api, env, role, n_clusters):
    """Non-operator roles see only clusters from their own account."""
    own_account, foreign_account = env.accounts(count=2)
    own_clusters = env.clusters(account=own_account, count=n_clusters)
    env.clusters(account=foreign_account, count=3)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_clusters(api, headers)

    assert_exact_clusters(response_body, own_clusters, account=own_account)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_ignores_foreign_account_id_filter(api, env, role):
    """Foreign account filters should be ignored for non-operators."""
    own_account, foreign_account = env.accounts(count=2)
    own_clusters = env.clusters(account=own_account, count=2)
    env.clusters(account=foreign_account, count=4)

    headers = HeadersPayload.build(
        account=own_account.name,
        role=role,
        user=f"{own_account.name}@ex.com",
    )
    response_body = list_clusters(
        api,
        headers,
        query={"account_id": foreign_account.id},
    )

    assert_exact_clusters(response_body, own_clusters, account=own_account)


@pytest.mark.parametrize("n_clusters", [1, 3])
def test_operator_filters_by_account_id(api, env, n_clusters):
    """Operator can filter clusters by account id."""
    noise_account, target_account, extra_noise_account = env.accounts(count=3)
    target_clusters = env.clusters(account=target_account, count=n_clusters)
    env.clusters(account=noise_account, count=2)
    env.clusters(account=extra_noise_account, count=4)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clusters(
        api,
        headers,
        query={"account_id": target_account.id},
    )

    assert_exact_clusters(response_body, target_clusters, account=target_account)


def test_operator_filters_by_cluster_name(api, env):
    """Operator can filter clusters by exact cluster name."""
    target_account = env.account()
    clusters = env.clusters(account=target_account, count=3)
    selected_cluster = clusters[1]

    headers = HeadersPayload.build(operator=True)
    response_body = list_clusters(
        api,
        headers,
        query={"name": selected_cluster.name},
    )

    assert_exact_clusters(response_body, [selected_cluster], account=target_account)


def test_operator_filter_by_missing_name_returns_empty_list(api, env):
    """Filtering by an unknown cluster name should return an empty list."""
    target_account = env.account()
    env.clusters(account=target_account, count=2)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clusters(
        api,
        headers,
        query={"name": "cluster-deadbeef"},
    )

    assert response_body == []


def test_operator_filters_by_account_id(api, env):
    """Operator can filter clusters by account relation id."""
    noise_account, target_account, extra_noise_account = env.accounts(count=3)
    env.cluster(account=noise_account)
    target_clusters = env.clusters(account=target_account, count=2)
    env.clusters(account=extra_noise_account, count=3)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clusters(
        api,
        headers,
        query={"account_id": target_account.id},
    )

    assert_exact_clusters(response_body, target_clusters, account=target_account)


def test_operator_filters_by_account_id_and_name(api, env):
    """Operator can combine account and cluster filters."""
    target_account, noise_account = env.accounts(count=2)
    target_clusters = env.clusters(account=target_account, count=3)
    selected_cluster = target_clusters[0]
    env.clusters(account=noise_account, count=2)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clusters(
        api,
        headers,
        query={"account_id": target_account.id, "name": selected_cluster.name},
    )

    assert_single_cluster(response_body, selected_cluster)
    assert response_body[0]["account"]["id"] == target_account.id


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_filters_own_cluster_by_name(api, env, role):
    """Non-operators can filter only within their own account."""
    own_account = env.account()
    clusters = env.clusters(account=own_account, count=3)
    selected_cluster = clusters[2]

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_clusters(
        api,
        headers,
        query={"name": selected_cluster.name},
    )

    assert_single_cluster(response_body, selected_cluster)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_cannot_reach_foreign_cluster_by_name(api, env, role):
    """Foreign cluster names should still return no results for non-operators."""
    own_account, foreign_account = env.accounts(count=2)
    env.clusters(account=own_account, count=2)
    foreign_clusters = env.clusters(account=foreign_account, count=3)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_clusters(
        api,
        headers,
        query={"name": foreign_clusters[0].name},
    )

    assert response_body == []


@pytest.mark.parametrize(
    "children_layout",
    [
        pytest.param(
            [{"target_pool_names": ["nvme"], "gateway_count": 2}],
            id="single-cluster",
        ),
        pytest.param(
            [
                {"target_pool_names": ["nvme", "ssd"], "gateway_count": 2},
                {"target_pool_names": ["ssd"], "gateway_count": 1},
                {"target_pool_names": [], "gateway_count": 0},
            ],
            id="mixed-clusters",
        ),
    ],
)
def test_operator_list_preserves_cluster_children_layout(api, env, children_layout):
    """Operator gets clusters with the expected gateway and target layout."""
    noise_account, target_account, extra_noise_account = env.accounts(count=3)
    env.clusters(account=noise_account, count=2)
    env.cluster(account=extra_noise_account)

    target_clusters = env.clusters(
        account=target_account,
        count=len(children_layout),
    )
    create_cluster_children(env, target_clusters, children_layout)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clusters(
        api,
        headers,
        query={"account_id": target_account.id},
    )

    assert_exact_clusters(response_body, target_clusters, account=target_account)
    assert_cluster_children_layout(response_body, target_clusters, children_layout)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_filters_own_cluster_with_children(api, env, role):
    """Non-operators still receive related gateways and targets for own cluster."""
    own_account = env.account()
    clusters = env.clusters(account=own_account, count=3)
    selected_cluster = clusters[1]
    env.targets(cluster=selected_cluster, pool_names=["nvme", "ssd"])
    env.gateways(cluster=selected_cluster, count=2)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_clusters(
        api,
        headers,
        query={"name": selected_cluster.name},
    )

    assert_single_cluster(response_body, selected_cluster)
    assert len(response_body[0]["gateways"]) == 2
