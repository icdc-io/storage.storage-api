import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiClientPayload
from tests.schemes.iscsi_client import IscsiClientResponseTestSchema


def validate_schema(body):
    """Validate response body against iSCSI client test schema."""
    try:
        IscsiClientResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_roles_can_create_client(api, account, role):
    """Non-operator roles should successfully create iSCSI client."""
    payload = IscsiClientPayload.build(account_name=account.name)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 201
    validate_schema(body)


def test_operator_role_can_create_client(api, account):
    """Operator role should successfully create iSCSI client."""
    payload = IscsiClientPayload.build(account_name=account.name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 201
    validate_schema(body)


# IQN validation tests


@pytest.mark.parametrize(
    "valid_iqn",
    [
        "iqn.2024-01.com.exmp:client0001",
        "iqn.2024-05.org.storage:target1234",
        "iqn.2023-12.kz.local:alpha9999",
        "iqn.2020-07.io.dev:myclientabcd",
    ],
)
def test_create_client_with_valid_iqn_returns_201(api, account, valid_iqn):
    """Valid IQN format should be accepted."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        iqn=valid_iqn,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status in (200, 201)
    validate_schema(body)


@pytest.mark.parametrize(
    "invalid_iqn",
    [
        "iqn2024-01.com.example:client1",
        "IQN.2024-01.com.example:client",
        "iqn.2024.com.example",
        "iqn.2024-01:client",
        "client0001",
        "",
        None,
    ],
)
def test_create_client_with_invalid_iqn_returns_400(
    api,
    account,
    invalid_iqn,
):
    """Invalid IQN format should be rejected with 400."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        iqn=invalid_iqn,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert "iqn" in str(body).lower()


# Name validation tests


@pytest.mark.parametrize(
    "valid_name",
    [
        "client_name",
        "client-01",
        "client.name_2",
        "a" * 24,
    ],
)
def test_create_client_with_valid_name_returns_201(
    api,
    account,
    valid_name,
):
    """Valid client name should be accepted."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        name=valid_name,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status in (200, 201)
    validate_schema(body)


@pytest.mark.parametrize(
    "invalid_name",
    [
        "client_name@",
        "client name",
        "A" * 25,
        "",
        None,
        "test/invalid",
    ],
)
def test_create_client_with_invalid_name_returns_400(
    api,
    account,
    invalid_name,
):
    """Invalid client name should be rejected with 400."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        name=invalid_name,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert "name" in str(body).lower()


# CHAP username validation tests


@pytest.mark.parametrize(
    "valid_username",
    [
        "chap.user",
        "chap_user",
        "chap-user",
        "chapuser",
        "test@chap.com",
        "test:chap",
        "test@chap:1",
        "a" * 64,
    ],
)
def test_create_client_with_valid_chap_username_returns_201(
    api,
    account,
    valid_username,
):
    """Valid CHAP username should be accepted."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        chap_username=valid_username,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status in (200, 201)
    validate_schema(body)


@pytest.mark.parametrize(
    "invalid_username",
    [
        "chap username",
        "A" * 65,
        "",
        None,
        "test/",
        "test\\",
    ],
)
def test_create_client_with_invalid_chap_username_returns_400(
    api,
    account,
    invalid_username,
):
    """Invalid CHAP username should be rejected with 400."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        chap_username=invalid_username,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert "chap_username" in str(body).lower()


# CHAP password validation tests


@pytest.mark.parametrize(
    "valid_password",
    [
        "A" * 12,
        "A" * 16,
        "chap.password",
        "test12345678",
        "valid@pass:12",
        "mixcase_1234",
    ],
)
def test_create_client_with_valid_chap_password_returns_201(
    api,
    account,
    valid_password,
):
    """Valid CHAP password should be accepted."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        chap_password=valid_password,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status in (200, 201)
    validate_schema(body)


@pytest.mark.parametrize(
    "invalid_password",
    [
        "short",
        "A" * 17,
        "",
        None,
        "bad\\password",
        "test#password",
    ],
)
def test_create_client_with_invalid_chap_password_returns_400(
    api,
    account,
    invalid_password,
):
    """Invalid CHAP password should be rejected with 400."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        chap_password=invalid_password,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert "chap_password" in str(body).lower()


# Owner email validation tests


@pytest.mark.parametrize(
    "valid_email",
    [
        "user@example.com",
        "test+tag@domain.org",
        "test_user@sub.domain.com",
    ],
)
def test_create_client_with_valid_owner_email_returns_201(
    api,
    account,
    valid_email,
):
    """Valid owner email should be accepted."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        owner=valid_email,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status in (200, 201)
    validate_schema(body)


@pytest.mark.parametrize(
    "invalid_email",
    [
        "user",
        "user@",
        "@example.com",
        "user@domain",
        "user@domain.",
        "user@.domain",
        "",
        None,
    ],
)
def test_create_client_with_invalid_owner_email_returns_400(
    api,
    account,
    invalid_email,
):
    """Invalid owner email should be rejected with 400."""
    payload = IscsiClientPayload.build(
        account_name=account.name,
        owner=invalid_email,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert "owner" in str(body).lower()


# Required fields validation tests


@pytest.mark.parametrize(
    "missing_field",
    ["name", "chap_username", "chap_password", "iqn", "owner"],
)
def test_create_client_with_missing_required_field_returns_400(
    api,
    account,
    missing_field,
):
    """Missing required field should be rejected with 400."""
    kwargs = {missing_field: None}
    payload = IscsiClientPayload.build(
        account_name=account.name,
        **kwargs,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert any(
        keyword in str(body).lower()
        for keyword in ["missing", "required", "invalid"]
    )


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_create_client_with_unknown_field_returns_400(
    api,
    account,
    unknown_field,
):
    """Unknown field in payload should be rejected with 400."""
    kwargs = {unknown_field: "error"}
    headers = HeadersPayload.build(operator=True)
    payload = IscsiClientPayload.create(
        account_name=account.name,
        **kwargs,
    )

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 400
    assert unknown_field in str(body)


# Account name tests


def test_create_client_without_account_name_uses_subject_account(api):
    """Client without account name should be created for operator's account."""
    payload = IscsiClientPayload.build()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.create(payload=payload, hdr=headers)

    assert status == 201
    assert body["account"]["name"] == "devel"
    validate_schema(body)
