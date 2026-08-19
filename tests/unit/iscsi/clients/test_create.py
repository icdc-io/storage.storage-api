import pytest
from marshmallow import ValidationError

from app.models.iscsi_client import IscsiClientSchema


def make_create_client_body(**overrides):
    body = {
        "name": "client_name",
        "chap_username": "chap.user",
        "chap_password": "A" * 12,
        "iqn": "iqn.2024-01.com.example:client0001",
        "owner": "user@example.com",
        "account_id": 1,
    }
    body.update(overrides)
    return body


# Field validation


@pytest.mark.parametrize(
    "valid_iqn",
    [
        "iqn.2024-01.com.exmp:client0001",
        "iqn.2024-05.org.storage:target1234",
        "iqn.2023-12.kz.local:alpha9999",
        "iqn.2020-07.io.dev:myclientabcd",
    ],
)
def test_client_schema_accepts_valid_iqn(valid_iqn):
    loaded = IscsiClientSchema().load(make_create_client_body(iqn=valid_iqn))

    assert loaded["iqn"] == valid_iqn


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
def test_client_schema_rejects_invalid_iqn(invalid_iqn):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(make_create_client_body(iqn=invalid_iqn))

    assert "iqn" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_name",
    [
        "client_name",
        "client-01",
        "client.name_2",
        "a" * 24,
    ],
)
def test_client_schema_accepts_valid_name(valid_name):
    loaded = IscsiClientSchema().load(make_create_client_body(name=valid_name))

    assert loaded["name"] == valid_name


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
def test_client_schema_rejects_invalid_name(invalid_name):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(make_create_client_body(name=invalid_name))

    assert "name" in exc_info.value.messages


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
def test_client_schema_accepts_valid_chap_username(valid_username):
    loaded = IscsiClientSchema().load(
        make_create_client_body(chap_username=valid_username)
    )

    assert loaded["chap_username"] == valid_username


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
def test_client_schema_rejects_invalid_chap_username(invalid_username):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(
            make_create_client_body(chap_username=invalid_username)
        )

    assert "chap_username" in exc_info.value.messages


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
def test_client_schema_accepts_valid_chap_password(valid_password):
    loaded = IscsiClientSchema().load(
        make_create_client_body(chap_password=valid_password)
    )

    assert loaded["chap_password"] == valid_password


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
def test_client_schema_rejects_invalid_chap_password(invalid_password):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(
            make_create_client_body(chap_password=invalid_password)
        )

    assert "chap_password" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_email",
    [
        "user@example.com",
        "test+tag@domain.org",
        "test_user@sub.domain.com",
    ],
)
def test_client_schema_accepts_valid_owner_email(valid_email):
    loaded = IscsiClientSchema().load(make_create_client_body(owner=valid_email))

    assert loaded["owner"] == valid_email


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
def test_client_schema_rejects_invalid_owner_email(invalid_email):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(make_create_client_body(owner=invalid_email))

    assert "owner" in exc_info.value.messages


@pytest.mark.parametrize("valid_account_id", [1, 2, 999])
def test_client_schema_accepts_valid_account_id(valid_account_id):
    loaded = IscsiClientSchema().load(
        make_create_client_body(account_id=valid_account_id)
    )

    assert loaded["account_id"] == valid_account_id


@pytest.mark.parametrize("invalid_account_id", ["bad", None])
def test_client_schema_rejects_invalid_account_id(invalid_account_id):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(
            make_create_client_body(account_id=invalid_account_id)
        )

    assert "account_id" in exc_info.value.messages


@pytest.mark.parametrize(
    "missing_field",
    ["name", "chap_username", "chap_password", "iqn", "owner", "account_id"],
)
def test_client_schema_rejects_missing_required_field(missing_field):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(make_create_client_body(**{missing_field: None}))

    assert missing_field in exc_info.value.messages


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_client_schema_rejects_unknown_field(unknown_field):
    payload = make_create_client_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema().load(payload)

    assert unknown_field in exc_info.value.messages
