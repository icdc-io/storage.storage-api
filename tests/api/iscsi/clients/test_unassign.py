import pytest

from tests.factories.headers import HeadersPayload


def make_assigned_client_disk(env, *, client_owner=None, disk_owner=None, pool_name="nvme"):
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
    env.assign(client=client, disks=disk)
    return account, client, disk


def test_member_can_unassign_own_client_and_disk(api, env):
    """Member can unassign disk from their own client."""
    account, client, disk = make_assigned_client_disk(env)

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204


def test_member_cannot_unassign_non_own_client(api, env):
    """Member cannot unassign disk from client they do not own."""
    account, client, disk = make_assigned_client_disk(
        env,
        client_owner="client_owner@example.com",
        disk_owner="disk_owner@example.com",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=disk.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


def test_member_cannot_unassign_non_own_disk(api, env):
    """Member cannot unassign disk they do not own."""
    account, client, disk = make_assigned_client_disk(
        env,
        client_owner="client_owner@example.com",
        disk_owner="disk_owner@example.com",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_or_owner_can_unassign_disk_in_own_account(api, env, role):
    """Admin/Owner can unassign disk in their own account."""
    account, client, disk = make_assigned_client_disk(env)

    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=disk.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_or_owner_cannot_unassign_disk_in_other_account(api, env, role):
    """Admin/Owner cannot unassign disk in another account."""
    _, client, disk = make_assigned_client_disk(env)
    foreign_account = env.account()

    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=disk.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


def test_operator_can_unassign_disk_in_any_account(api, env):
    """Operator can unassign disk in any account."""
    _, client, disk = make_assigned_client_disk(env)

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204


def test_unassign_disk_from_nonexistent_client_returns_404(api, env):
    """Unassigning disk from non-existent client should return 404."""
    account = env.account()
    scope_ctx = env.scope(account=account, pool_name="nvme")
    disk = env.disk(target=scope_ctx.target)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=0,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


def test_unassign_nonexistent_disk_from_client_returns_404(api, env):
    """Unassigning non-existent disk from client should return 404."""
    account = env.account()
    client = env.client(account=account)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=0,
        header=headers,
    )

    assert status == 404


def test_unassign_already_unassigned_disk_succeeds(api, env):
    """Unassigning already unassigned disk should succeed (idempotent)."""
    account = env.account()
    client = env.client(account=account)
    scope_ctx = env.scope(account=account, pool_name="nvme")
    disk = env.disk(target=scope_ctx.target)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204
