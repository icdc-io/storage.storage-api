import pytest
from marshmallow import ValidationError

from app.models.iscsi_client import IscsiClients
from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiClientPayload
from tests.schemes.iscsi_client import IscsiClientResponseTestSchema


def validate_schema(body):
    """Validate response body against iSCSI client test schema."""
    try:
        IscsiClientResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")


def test_create_client_with_real_db_state(api, env):
    account = env.account()

    payload = IscsiClientPayload.build(
        account_name=account.name,
        name="client-aaaa1000",
        iqn="iqn.2024-01.com.example:client1000",
        chap_username="user1000",
        chap_password="password1000",
        owner="owner_client0@example.com",
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, header=headers)

    assert status in (200, 201)
    validate_schema(body)
    assert body["name"] == payload["name"]
    assert body["iqn"] == payload["iqn"]
    assert body["owner"] == payload["owner"]
    assert body["account"]["name"] == account.name

    client = IscsiClients.query.filter_by(id=body["id"]).first()
    assert client is not None
    assert client.account_id == account.id
    assert client.name == payload["name"]
    assert client.iqn == payload["iqn"]
    assert client.owner == payload["owner"]


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_roles_can_create_client_in_own_account(api, env, role):
    """Owner, admin, and member can create a client in their own account."""
    account = env.account()
    payload = IscsiClientPayload.build(account_name=account.name)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.clients.create(payload=payload, header=headers)

    assert status == 201
    validate_schema(body)
    assert body["account"]["name"] == account.name


def test_operator_can_create_client_in_any_account(api, env):
    """Operator can create a client for another account using the devel account."""
    account = env.account()
    payload = IscsiClientPayload.build(account_name=account.name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, header=headers)

    assert status == 201
    validate_schema(body)
    assert body["account"]["name"] == account.name


# Account name tests


def test_create_client_without_account_name_uses_subject_account(api):
    """Client without account name should be created for operator's account."""
    payload = IscsiClientPayload.build()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, header=headers)

    assert status == 201
    assert body["account"]["name"] == "devel"
    validate_schema(body)
