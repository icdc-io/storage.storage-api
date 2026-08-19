import pytest
from marshmallow import ValidationError

from app.models.iscsi_client import IscsiClientSchema


def make_update_client_body(**overrides):
    body = {
        "name": "client_name",
        "chap_username": "chap.user",
        "chap_password": "A" * 12,
        "owner": "user@example.com",
    }
    body.update(overrides)
    return body


# Field validation


@pytest.mark.parametrize(
    "valid_name",
    [
        "client_name",
        "client-01",
        "client.name_2",
        "a" * 24,
    ],
)
def test_update_client_schema_accepts_valid_name(valid_name):
    loaded = IscsiClientSchema(partial=True).load(
        make_update_client_body(name=valid_name)
    )

    assert loaded["name"] == valid_name


@pytest.mark.parametrize(
    "invalid_name",
    [
        "client name",
        "client_name@",
        "A" * 25,
        "",
        None,
        "test/invalid",
    ],
)
def test_update_client_schema_rejects_invalid_name(invalid_name):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema(partial=True).load(
            make_update_client_body(name=invalid_name)
        )

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
def test_update_client_schema_accepts_valid_chap_username(valid_username):
    loaded = IscsiClientSchema(partial=True).load(
        make_update_client_body(chap_username=valid_username)
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
def test_update_client_schema_rejects_invalid_chap_username(invalid_username):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema(partial=True).load(
            make_update_client_body(chap_username=invalid_username)
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
def test_update_client_schema_accepts_valid_chap_password(valid_password):
    loaded = IscsiClientSchema(partial=True).load(
        make_update_client_body(chap_password=valid_password)
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
def test_update_client_schema_rejects_invalid_chap_password(invalid_password):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema(partial=True).load(
            make_update_client_body(chap_password=invalid_password)
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
def test_update_client_schema_accepts_valid_owner_email(valid_email):
    loaded = IscsiClientSchema(partial=True).load(
        make_update_client_body(owner=valid_email)
    )

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
def test_update_client_schema_rejects_invalid_owner_email(invalid_email):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema(partial=True).load(
            make_update_client_body(owner=invalid_email)
        )

    assert "owner" in exc_info.value.messages


def test_update_client_schema_accepts_empty_payload():
    loaded = IscsiClientSchema(partial=True).load({})

    assert loaded == {}


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_update_client_schema_rejects_unknown_field(unknown_field):
    payload = make_update_client_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        IscsiClientSchema(partial=True).load(payload)

    assert unknown_field in exc_info.value.messages
