import pytest

from tests.factories.headers import HeadersPayload
from tests.schemes import IscsiClientResponseTestSchema
from tests.support.assertions import assert_schema_response


def validate_response(body, schema=IscsiClientResponseTestSchema, many=True):
    assert_schema_response(body, schema, many=many)


def list_clients(api, headers, query=None):
    status_code, response_body = api.iscsi.clients.list(query=query, header=headers)

    assert status_code == 200
    validate_response(response_body)
    return response_body


def assert_client_ids(response_body, clients):
    assert {item["id"] for item in response_body} == {client.id for client in clients}


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_list_only_own_account_clients(api, env, role):
    """Owner and admin should only see clients from their own account."""
    own_account, foreign_account = env.accounts(count=2)
    own_client_one = env.client(account=own_account)
    own_client_two = env.client(account=own_account)
    env.client(account=foreign_account)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_clients(api, headers)

    assert_client_ids(response_body, [own_client_one, own_client_two])


def test_member_lists_only_own_clients(api, env):
    """Member should only see clients owned by the authenticated user."""
    account, foreign_account = env.accounts(count=2)
    member_owner = "member-client-owner@example.com"
    own_client_one = env.client(account=account, owner=member_owner)
    own_client_two = env.client(account=account, owner=member_owner)
    env.client(account=account, owner="same-account-other@example.com")
    env.client(account=foreign_account, owner=member_owner)

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_clients(api, headers)

    assert_client_ids(response_body, [own_client_one, own_client_two])


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_ignores_foreign_account_filter(api, env, role):
    """Account-scoped roles should not widen scope with foreign account filters."""
    own_account, foreign_account = env.accounts(count=2)
    own_client = env.client(account=own_account)
    env.client(account=foreign_account)

    headers_kwargs = {"account": own_account.name, "role": role}
    if role == "member":
        headers_kwargs["user"] = own_client.owner
    headers = HeadersPayload.build(**headers_kwargs)

    response_body = list_clients(
        api,
        headers,
        query={"account_id": foreign_account.id},
    )

    assert_client_ids(response_body, [own_client])


def test_member_owner_filter_does_not_override_subject_scope(api, env):
    """Member owner filter should not override authenticated owner scope."""
    account = env.account()
    member_owner = "member-client-filter@example.com"
    own_client = env.client(account=account, owner=member_owner)
    foreign_owner_client = env.client(
        account=account,
        owner="other-client-owner@example.com",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_clients(
        api,
        headers,
        query={"owner": foreign_owner_client.owner},
    )

    assert_client_ids(response_body, [own_client])


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_account_filter_does_not_override_scope(api, env, role):
    """Owner/admin should not reach a foreign account through account_id filter."""
    own_account, foreign_account = env.accounts(count=2)
    own_client = env.client(account=own_account)
    env.client(account=foreign_account)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_clients(
        api,
        headers,
        query={"account_id": foreign_account.id, "id": own_client.id},
    )

    assert_client_ids(response_body, [own_client])


def test_operator_filters_clients_by_name(api, env):
    """Operator should be able to filter clients by name."""
    account = env.account()
    matching_client = env.client(account=account)
    env.client(account=account)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clients(
        api,
        headers,
        query={"name": matching_client.name},
    )

    assert_client_ids(response_body, [matching_client])


def test_operator_filters_clients_by_owner(api, env):
    """Operator should be able to filter clients by owner."""
    account = env.account()
    matching_owner = "client-owner-filter@example.com"
    matching_client = env.client(account=account, owner=matching_owner)
    env.client(account=account, owner="other-owner-filter@example.com")

    headers = HeadersPayload.build(operator=True)
    response_body = list_clients(
        api,
        headers,
        query={"owner": matching_owner},
    )

    assert_client_ids(response_body, [matching_client])


def test_operator_combines_account_and_base_filters(api, env):
    """Operator should get the exact intersection of account and client filters."""
    target_account, other_account = env.accounts(count=2)
    matching_owner = "client-combo-owner@example.com"
    matching_client = env.client(account=target_account, owner=matching_owner)
    env.client(account=target_account, owner="client-combo-other@example.com")
    env.client(account=other_account, owner=matching_owner)

    headers = HeadersPayload.build(operator=True)
    response_body = list_clients(
        api,
        headers,
        query={
            "account_id": target_account.id,
            "owner": matching_owner,
        },
    )

    assert_client_ids(response_body, [matching_client])


def test_list_client_includes_assigned_disks_in_response_body(api, env):
    """Client list should serialize assigned disks for the returned client."""
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
    response_body = list_clients(
        api,
        headers,
        query={"id": client.id},
    )

    assert len(response_body) == 1
    assert response_body[0]["id"] == client.id
    assert {item["id"] for item in response_body[0]["disks"]} == {disk.id}
    assert response_body[0]["disks"][0]["name"] == disk.name
    assert response_body[0]["disks"][0]["owner"] == disk.owner
