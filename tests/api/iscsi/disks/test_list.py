import pytest

from tests.factories.headers import HeadersPayload
from tests.schemes import IscsiDiskResponseTestSchema
from tests.support.assertions import assert_schema_response


def validate_response(body, schema=IscsiDiskResponseTestSchema, many=True):
    assert_schema_response(body, schema, many=many)


def list_disks(api, headers, query=None):
    status_code, response_body = api.iscsi.disks.list(query=query, header=headers)

    assert status_code == 200
    validate_response(response_body)
    return response_body


def assert_disk_ids(response_body, disks):
    assert {item["id"] for item in response_body} == {disk.id for disk in disks}


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_list_only_own_account_disks(api, env, role):
    """Owner and admin should only see disks from their own account."""
    own_account, foreign_account = env.accounts(count=2)
    own_nvme_scope = env.scope(account=own_account, pool_name="nvme")
    own_ssd_scope = env.scope(account=own_account, pool_name="ssd")
    foreign_scope = env.scope(account=foreign_account)

    own_disk_one = env.disk(target=own_nvme_scope.target)
    own_disk_two = env.disk(target=own_ssd_scope.target)
    env.disk(target=foreign_scope.target)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_disks(api, headers)

    assert_disk_ids(response_body, [own_disk_one, own_disk_two])


def test_member_lists_only_own_disks(api, env):
    """Member should only see disks owned by the authenticated user."""
    account, foreign_account = env.accounts(count=2)
    member_owner = "member-visible@example.com"
    nvme_scope = env.scope(account=account, pool_name="nvme")
    ssd_scope = env.scope(account=account, pool_name="ssd")
    foreign_scope = env.scope(account=foreign_account)

    own_disk_one = env.disk(target=nvme_scope.target, owner=member_owner)
    own_disk_two = env.disk(target=ssd_scope.target, owner=member_owner)
    env.disk(target=nvme_scope.target, owner="same-account-other@example.com")
    env.disk(target=foreign_scope.target, owner=member_owner)

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_disks(api, headers)

    assert_disk_ids(response_body, [own_disk_one, own_disk_two])


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_ignores_foreign_account_filter(api, env, role):
    """Account-scoped roles should not widen scope with foreign account filters."""
    own_account, foreign_account = env.accounts(count=2)
    own_scope = env.scope(account=own_account)
    foreign_scope = env.scope(account=foreign_account)
    own_disk = env.disk(target=own_scope.target)
    env.disk(target=foreign_scope.target)

    headers_kwargs = {"account": own_account.name, "role": role}
    if role == "member":
        headers_kwargs["user"] = own_disk.owner
    headers = HeadersPayload.build(**headers_kwargs)

    response_body = list_disks(
        api,
        headers,
        query={"account_id": foreign_account.id},
    )

    assert_disk_ids(response_body, [own_disk])


def test_member_owner_filter_does_not_override_subject_scope(api, env):
    """Member owner filter should not override authenticated owner scope."""
    account = env.account()
    member_owner = "member-owner@example.com"
    scope = env.scope(account=account)
    own_disk = env.disk(target=scope.target, owner=member_owner)
    foreign_owner_disk = env.disk(
        target=scope.target,
        owner="other-owner@example.com",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_disks(
        api,
        headers,
        query={"owner": foreign_owner_disk.owner},
    )

    assert_disk_ids(response_body, [own_disk])


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_account_filter_does_not_override_scope(api, env, role):
    """Owner/admin should not reach a foreign account through account_id filter."""
    own_account, foreign_account = env.accounts(count=2)
    own_scope = env.scope(account=own_account)
    foreign_scope = env.scope(account=foreign_account)
    own_disk = env.disk(target=own_scope.target)
    env.disk(target=foreign_scope.target)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_disks(
        api,
        headers,
        query={"account_id": foreign_account.id, "id": own_disk.id},
    )

    assert_disk_ids(response_body, [own_disk])


def test_operator_filters_disks_by_cluster_name(api, env):
    """Operator should be able to filter disks by parent cluster name."""
    target_account, other_account = env.accounts(count=2)
    selected_cluster = env.cluster(account=target_account)
    other_cluster = env.cluster(account=target_account)
    selected_scope = env.scope(
        cluster=selected_cluster,
        pool_name="nvme",
    )
    other_cluster_scope = env.scope(
        cluster=other_cluster,
        pool_name="ssd",
    )
    other_account_scope = env.scope(account=other_account)
    matching_disk = env.disk(target=selected_scope.target)
    env.disk(target=other_cluster_scope.target)
    env.disk(target=other_account_scope.target)

    headers = HeadersPayload.build(operator=True)
    response_body = list_disks(
        api,
        headers,
        query={"cluster.name": selected_cluster.name},
    )

    assert_disk_ids(response_body, [matching_disk])


def test_operator_filters_disks_by_pool_class(api, env):
    """Operator should be able to filter disks by parent pool class."""
    account = env.account()
    ssd_scope = env.scope(account=account, pool_name="ssd")
    nvme_scope = env.scope(account=account, pool_name="nvme")
    matching_disk = env.disk(target=ssd_scope.target)
    env.disk(target=nvme_scope.target)

    headers = HeadersPayload.build(operator=True)
    response_body = list_disks(
        api,
        headers,
        query={"account_id": account.id, "pool.class": "ssd"},
    )

    assert_disk_ids(response_body, [matching_disk])


def test_member_relation_filter_still_respects_owner_scope(api, env):
    """Relation filters should narrow member results, not widen them."""
    account = env.account()
    member_owner = "member-cluster-owner@example.com"
    selected_cluster = env.cluster(account=account)
    other_cluster = env.cluster(account=account)
    selected_scope = env.scope(
        cluster=selected_cluster,
        pool_name="nvme",
    )
    other_scope = env.scope(
        cluster=other_cluster,
        pool_name="ssd",
    )

    matching_disk = env.disk(
        target=selected_scope.target,
        owner=member_owner,
    )
    env.disk(
        target=selected_scope.target,
        owner="same-cluster-other-owner@example.com",
    )
    env.disk(
        target=other_scope.target,
        owner=member_owner,
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_disks(
        api,
        headers,
        query={"cluster.name": selected_cluster.name},
    )

    assert_disk_ids(response_body, [matching_disk])


def test_operator_combines_base_and_parent_filters(api, env):
    """Operator should get the exact intersection of base and parent filters."""
    account = env.account()
    selected_cluster = env.cluster(account=account)
    other_cluster = env.cluster(account=account)
    selected_scope = env.scope(
        cluster=selected_cluster,
        pool_name="nvme",
    )
    other_scope = env.scope(
        cluster=other_cluster,
        pool_name="ssd",
    )

    matching_disk = env.disk(
        target=selected_scope.target,
        owner="combo-owner@example.com",
    )
    env.disk(
        target=selected_scope.target,
        owner="other-owner@example.com",
    )
    env.disk(
        target=other_scope.target,
        owner="combo-owner@example.com",
    )

    headers = HeadersPayload.build(operator=True)
    response_body = list_disks(
        api,
        headers,
        query={
            "owner": matching_disk.owner,
            "cluster.name": selected_cluster.name,
        },
    )

    assert_disk_ids(response_body, [matching_disk])


def test_list_disk_includes_assigned_clients_in_response_body(api, env):
    """Disk list should serialize assigned clients for the returned disk."""
    account = env.account()
    client = env.client(account=account)
    scope = env.scope(account=account)
    disk = env.disk(target=scope.target, owner=client.owner)
    env.assign(client=client, disks=disk)

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )
    response_body = list_disks(
        api,
        headers,
        query={"id": disk.id},
    )

    assert len(response_body) == 1
    assert response_body[0]["id"] == disk.id
    assert {item["id"] for item in response_body[0]["clients"]} == {client.id}
    assert response_body[0]["clients"][0]["name"] == client.name
    assert response_body[0]["clients"][0]["iqn"] == client.iqn
