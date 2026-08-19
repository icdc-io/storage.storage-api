import pytest
from marshmallow import ValidationError

from app.models.iscsi_cluster import IscsiClusterSchema
from tests.factories.iscsi_cluster import IscsiClusterPayload


def make_create_cluster_body(**overrides):
    account_id = overrides.pop("account_id", 1)
    body = IscsiClusterPayload.build(account_name="unitacct", **overrides)
    body["account_id"] = account_id
    body.pop("account_name", None)
    return body


@pytest.mark.parametrize(
    "good_name",
    [
        "cluster-00000000",
        "cluster-ffffffff",
        "cluster-deabbeef",
        "cluster-1234abcd",
        "cluster-abcdef12",
        "cluster-00ff00ff",
        "cluster-a1b2c3d4",
        "cluster-01020304",
        "cluster-c0ffee00",
        "cluster-bad1cafe",
        "cluster-5e1fd0c0",
        "cluster-0a1b2c3d",
    ],
)
def test_cluster_schema_accepts_valid_name(good_name):
    loaded = IscsiClusterSchema().load(make_create_cluster_body(name=good_name))

    assert loaded["name"] == good_name


@pytest.mark.parametrize(
    "bad_name",
    [
        "cluster-test1234",
        "cluster-XYZ12345",
        "cluster-1234567",
        "cluster-123456789",
        "cluster_abcdef12",
        "cluster-abc1234g",
        "cluster-",
        "cluster",
        "c0ffee00"
        "",
        None,
    ],
)
def test_cluster_schema_rejects_invalid_name(bad_name):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClusterSchema().load(make_create_cluster_body(name=bad_name))

    assert "name" in exc_info.value.messages


@pytest.mark.parametrize("valid_account_id", [1, 2, 999])
def test_cluster_schema_accepts_valid_account_id(valid_account_id):
    loaded = IscsiClusterSchema().load(
        make_create_cluster_body(account_id=valid_account_id)
    )

    assert loaded["account_id"] == valid_account_id


@pytest.mark.parametrize("invalid_account_id", ["bad", None])
def test_cluster_schema_rejects_invalid_account_id(invalid_account_id):
    with pytest.raises(ValidationError) as exc_info:
        IscsiClusterSchema().load(
            make_create_cluster_body(account_id=invalid_account_id)
        )

    assert "account_id" in exc_info.value.messages


def test_cluster_schema_rejects_missing_account_id():
    with pytest.raises(ValidationError) as exc_info:
        IscsiClusterSchema().load({"name": "cluster-abcdef12"})

    assert "account_id" in exc_info.value.messages


def test_cluster_schema_rejects_missing_name():
    with pytest.raises(ValidationError) as exc_info:
        IscsiClusterSchema().load({"account_id": 1})

    assert "name" in exc_info.value.messages


def test_cluster_schema_rejects_extra_field():
    payload = make_create_cluster_body()
    payload["extra_field"] = "error"

    with pytest.raises(ValidationError) as exc_info:
        IscsiClusterSchema().load(payload)

    assert "extra_field" in exc_info.value.messages
