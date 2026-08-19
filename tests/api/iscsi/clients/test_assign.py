import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiAssignedClientPayload


def make_client_and_disk(env, *, client_owner=None, disk_owner=None, pool_name="nvme"):
    account = env.account()
    client = env.client(
        account=account,
        owner=client_owner or "client_owner@example.com",
    )
    scope_ctx = env.scope(account=account, pool_name=pool_name)
    disk = env.disk(
        target=scope_ctx.target,
        owner=disk_owner or client.owner,
    )
    return account, client, disk


def test_member_can_assign_own_client_and_disk(api, env):
    """Member can assign a disk they own to their own client."""
    account, client, disk = make_client_and_disk(env)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 201, "Disk assigned successfully."
    assert disk in client.disks


def test_member_cannot_assign_non_own_client(api, env):
    """Member cannot assign a disk to a client they do not own."""
    account, client, disk = make_client_and_disk(
        env,
        client_owner="client_owner@example.com",
        disk_owner="disk_owner@example.com",
    )

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=disk.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Client not found."


def test_member_cannot_assign_non_own_disk(api, env):
    """Member cannot assign a disk they do not own, even for their own client."""
    account, client, disk = make_client_and_disk(
        env,
        client_owner="client_owner@example.com",
        disk_owner="disk_owner@example.com",
    )

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Disk not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_assign_account_client_and_disk(api, env, role):
    """Admin and owner can assign disks to a client in their own account."""
    account, client, disk = make_client_and_disk(env)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 201, "Disk assigned successfully."
    assert disk in client.disks


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_assign_client_in_other_account(api, env, role):
    """Member/admin/owner cannot assign disk to a client in another account."""
    owner_account, client, disk = make_client_and_disk(env)
    foreign_account = env.account()

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Client not found."


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_assign_disk_in_other_account(api, env, role):
    """Member/admin/owner cannot assign a disk that belongs to another account."""
    client_account = env.account()
    client = env.client(account=client_account)
    disk_account = env.account()
    scope_ctx = env.scope(account=disk_account, pool_name="nvme")
    disk = env.disk(target=scope_ctx.target, owner=client.owner)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=client_account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Disk not found."


def test_operator_can_assign_client_in_any_account(api, env):
    """Operator can assign disks to clients in any account."""
    account, client, disk = make_client_and_disk(env)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 201, "Disk assigned successfully."
    assert disk in client.disks


def test_operator_cannot_assign_client_and_disk_of_different_accounts(api, env):
    """Operator cannot assign disk and client from different accounts."""
    client_account = env.account()
    client = env.client(account=client_account)
    disk_account = env.account()
    scope_ctx = env.scope(account=disk_account, pool_name="nvme")
    disk = env.disk(target=scope_ctx.target)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 400


def test_assign_disk_to_nonexistent_client_returns_404(api, env):
    """Assigning disk to non-existent client should return 404."""
    account = env.account()
    scope_ctx = env.scope(account=account, pool_name="nvme")
    disk = env.disk(target=scope_ctx.target)
    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=0,
        payload=payload,
        header=headers,
    )

    assert status == 404
