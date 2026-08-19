import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiClientPayload
from tests.schemes import IscsiClientResponseTestSchema


def validate_schema(body):
    """Helper: validate response against schema."""
    try:
        IscsiClientResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")


def test_member_can_update_own_client(api, env):
    """Member can update their own iSCSI client."""
    account = env.account()
    client = env.client(account=account)
    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)


def test_member_cannot_update_non_own_client(api, env):
    """Member cannot update a client they do not own."""
    account = env.account()
    client = env.client(account=account)
    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        fake_user=True,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 404, "Client not found."


def test_member_cannot_change_owner(api, env):
    """Member cannot change owner of their own client."""
    account = env.account()
    client = env.client(account=account)
    old_owner = client.owner

    payload = IscsiClientPayload.build(changed_owner=True)
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
def test_admin_or_owner_can_update_client(api, env, role):
    """Admin/Owner can update client in their account."""
    account = env.account()
    client = env.client(account=account)
    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_update_client_in_other_account(
    api,
    env,
    role,
):
    """Any non-operator cannot update client in another account."""
    owner_account = env.account()
    client = env.client(account=owner_account)
    account = env.account()

    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 404, "Client not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_or_owner_can_change_owner(api, env, role):
    """Admin/Owner can change client owner."""
    account = env.account()
    client = env.client(account=account)
    old_owner = client.owner

    payload = IscsiClientPayload.build(changed_owner=True)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] != old_owner, "Owner must be changed."


def test_operator_can_update_client(api, env):
    """Operator can update client in any account."""
    account = env.account()
    client = env.client(account=account)
    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)


def test_operator_can_change_owner(api, env):
    """Operator can change client owner."""
    account = env.account()
    client = env.client(account=account)
    old_owner = client.owner

    payload = IscsiClientPayload.build(changed_owner=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] != old_owner, "Owner must be changed."


def test_update_nonexistent_client_returns_404(api):
    """Updating a nonexistent client returns 404."""
    payload = IscsiClientPayload.build()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(99999, payload, headers)

    assert status == 404
