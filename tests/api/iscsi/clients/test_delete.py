import pytest

from tests.factories.headers import HeadersPayload


def test_member_can_delete_own_client(api, env):
    """Member can delete their own iSCSI client."""
    account = env.account()
    client = env.client(account=account)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 204


def test_member_cannot_delete_non_own_client(api, env):
    """Member cannot delete a client they do not own."""
    account = env.account()
    client = env.client(account=account)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        fake_user=True,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 404, "Client not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_delete_account_client(api, env, role):
    """Admin and owner can delete clients in their own account."""
    account = env.account()
    client = env.client(account=account)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 204


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_delete_client_in_other_account(api, env, role):
    """Non-operator roles cannot delete client belonging to another account."""
    client_account, foreign_account = env.accounts(count=2)
    client = env.client(account=client_account)
    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 404, "Client not found."


def test_operator_can_delete_client_in_any_account(api, env):
    """Operator can delete client in any account."""
    account = env.account()
    client = env.client(account=account)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 204


def test_delete_client_with_assigned_disks_in_db_fails(api, env):
    """Deleting client with disks assigned in DB should fail with 409."""
    account = env.account()
    client = env.client(account=account)
    scope = env.scope(account=account)
    disk = env.disk(target=scope.target, owner=client.owner)
    env.assign(client=client, disks=disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 409
