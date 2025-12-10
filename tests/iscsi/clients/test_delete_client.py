import pytest

from tests.factories.headers import HeadersPayload
from tests.fixtures.iscsi_client import verify_client_exists


def test_member_can_delete_own_client(api, account, client):
    """Member can delete their own iSCSI client."""
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 204


def test_member_cannot_delete_non_own_client(api, account, client):
    """Member cannot delete a client they do not own."""
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        fake_user=True,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 404, "Client not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_delete_account_client(api, account, client, role):
    """Admin and owner can delete clients in their own account."""
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 204


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_delete_client_in_other_account(
    api,
    account_factory,
    client,
    role,
):
    """Non-operator roles cannot delete client belonging to another account."""
    account = account_factory(count=1)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 404, "Client not found."


def test_operator_can_delete_client_in_any_account(api, account, client):
    """Operator can delete client in any account."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 204


def test_delete_client_with_assigned_disks_in_db_fails(
    api,
    client,
    disk_db_factory,
    iscsi_pools,
    assigned_db_factory,
):
    """Deleting client with disks assigned in DB should fail with 409."""
    disks = disk_db_factory(disk_pools=iscsi_pools.keys())
    assigned_db_factory(clients=client, disks=disks)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.delete(client.id, headers)

    assert status == 409


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_delete_client_requires_unassign_in_single_pool(
    api,
    assigned_ceph_factory,
    ceph_unassign_client,
    pool_name,
):
    """Client cannot be deleted while disks are assigned in a single pool."""
    headers = HeadersPayload.build(operator=True)
    client = assigned_ceph_factory(disk_pools=pool_name)

    status, body = api.iscsi.clients.delete(client.id, headers)
    assert status == 409
    assert verify_client_exists(client, pool_name)

    ceph_unassign_client(client)

    status, body = api.iscsi.clients.delete(client.id, headers)
    assert status == 204
