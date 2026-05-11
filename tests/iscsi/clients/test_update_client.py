import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiClientPayload
from tests.fixtures.iscsi_client import verify_client_credentials
from tests.schemes import IscsiClientResponseTestSchema


def validate_schema(body):
    """Helper: validate response against schema."""
    try:
        IscsiClientResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")


def test_member_can_update_own_client(api, account, client):
    """Member can update their own iSCSI client."""
    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)


def test_member_cannot_update_non_own_client(api, account, client):
    """Member cannot update a client they do not own."""
    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        fake_user=True,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 404, "Client not found."


def test_member_cannot_change_owner(api, account, client):
    """Member cannot change owner of their own client."""
    old_owner = client.owner

    payload = IscsiClientPayload.build(new_owner=True)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] == old_owner, "Owner must not change."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_or_owner_can_update_client(api, account, client, role):
    """Admin/Owner can update client in their account."""
    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_update_client_in_other_account(
    api,
    account_factory,
    client,
    role,
):
    """Any non-operator cannot update client in another account."""
    account = account_factory()

    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 404, "Client not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_or_owner_can_change_owner(api, account, client, role):
    """Admin/Owner can change client owner."""
    old_owner = client.owner

    payload = IscsiClientPayload.build(new_owner=True)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] != old_owner, "Owner must be changed."


def test_operator_can_update_client(api, account, client):
    """Operator can update client in any account."""
    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)


def test_operator_can_change_owner(api, account, client):
    """Operator can change client owner."""
    old_owner = client.owner

    payload = IscsiClientPayload.build(new_owner=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] != old_owner, "Owner must be changed."


def test_update_client_name(api, account, client):
    """Client name can be successfully updated."""
    new_name = "new_client_name"

    payload = IscsiClientPayload.build(name=new_name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["name"] == new_name, "Client name must change."


def test_update_nonexistent_client_returns_404(api, client):
    """Updating a nonexistent client returns 404."""
    payload = IscsiClientPayload.build()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(99999, payload, headers)

    assert status == 404


@pytest.mark.ceph
def test_update_credentials_across_all_pools(
    api,
    assigned_ceph_factory,
    target_pools,
):
    """Update CHAP credentials for a client with disks across all pools."""
    client = assigned_ceph_factory(disk_pools="nvme")

    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    assert body["chap_username"] == payload["chap_username"]
    assert body["chap_password"] == payload["chap_password"]
    assert verify_client_credentials(client)


@pytest.mark.ceph
def test_update_credentials_in_multiple_pools(
    api,
    assigned_ceph_factory,
):
    """Update CHAP credentials for a client with nvme + ssd pools."""
    client = assigned_ceph_factory(disk_pools=["nvme", "ssd"])

    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    assert body["chap_username"] == payload["chap_username"]
    assert body["chap_password"] == payload["chap_password"]
    assert verify_client_credentials(client)


@pytest.mark.ceph
def test_update_credentials_for_unassigned_then_reassigned_client(
    api,
    client_ceph_assigned,
    ceph_unassign_client,
    assigned_ceph_factory,
):
    """Update credentials when unassigned, then reassign disk and verify."""
    disk = client_ceph_assigned.disks[0]

    # Step 1: Unassign all disks
    ceph_unassign_client(client_ceph_assigned, client_ceph_assigned.disks)

    # Step 2: Update credentials
    payload = IscsiClientPayload.build(chap=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(
        client_ceph_assigned.id,
        payload,
        headers,
    )

    assert status == 200
    assert body["chap_username"] == payload["chap_username"]
    assert body["chap_password"] == payload["chap_password"]

    # Step 3: Reassign disk
    assigned_ceph_factory(client_ceph_assigned, disks=[disk])

    # Step 4: Verify credentials propagated
    assert verify_client_credentials(client_ceph_assigned)
