import pytest
from marshmallow import ValidationError

from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema
from tests.unit.iscsi.quotas.test_create import make_limitset, quota_limits


def make_update_quota_body(**overrides):
    body = {
        "clients": 4,
        "data_size_gb": 20,
        "disks": 10,
        "snapshots": 6,
        "pool_id": 1,
    }
    body.update(overrides)
    return body


# Field validation


def test_update_iscsi_quota_schema_accepts_empty_payload():
    loaded = IscsiQuotaSchema(partial=True).load({})

    assert loaded == {}


@pytest.mark.parametrize("field", ["clients", "data_size_gb", "disks", "snapshots"])
def test_update_iscsi_quota_schema_accepts_valid_quota_field(field, quota_limits):
    loaded = IscsiQuotaSchema(partial=True).load(make_update_quota_body(**{field: 1}))

    assert loaded[field] == 1


@pytest.mark.parametrize("field", ["clients", "data_size_gb", "disks", "snapshots"])
@pytest.mark.parametrize("value", [-1, "bad", None])
def test_update_iscsi_quota_schema_rejects_invalid_quota_field(field, value, quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema(partial=True).load(make_update_quota_body(**{field: value}))

    assert field in exc_info.value.messages


def test_update_iscsi_quota_schema_rejects_unknown_field(quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema(partial=True).load(make_update_quota_body(extra_field="nope"))

    assert "extra_field" in exc_info.value.messages


def test_update_iscsi_quota_schema_accepts_without_pool_context():
    loaded = IscsiQuotaSchema(partial=True).load({"clients": 5})

    assert loaded == {"clients": 5}


# Limit and usage validation


@pytest.mark.parametrize(
    "field, limit, requested",
    [
        ("clients", 10, 11),
        ("data_size_gb", 100, 101),
        ("disks", 20, 21),
        ("snapshots", 30, 31),
    ],
)
def test_update_iscsi_quota_schema_rejects_value_over_pool_limit(
    field,
    limit,
    requested,
    monkeypatch,
    quota_limits,
):
    monkeypatch.setattr(
        IscsiQuotas,
        "get_pool_limitset",
        classmethod(lambda cls, pool_id: make_limitset(**{field: limit})),
    )

    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema(partial=True).load(make_update_quota_body(**{field: requested}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "field, usage, requested",
    [
        ("clients", 4, 3),
        ("data_size_gb", 12, 11),
        ("disks", 7, 6),
        ("snapshots", 5, 4),
    ],
)
def test_update_iscsi_quota_schema_rejects_value_below_current_usage(
    field,
    usage,
    requested,
    quota_limits,
):
    schema = IscsiQuotaSchema(
        context={
            "usage": {
                "clients": 0,
                "data_size_gb": 0,
                "disks": 0,
                "snapshots": 0,
            }
            | {field: usage}
        },
        partial=True,
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_update_quota_body(**{field: requested}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "field, usage",
    [
        ("clients", 4),
        ("data_size_gb", 12),
        ("disks", 7),
        ("snapshots", 5),
    ],
)
def test_update_iscsi_quota_schema_accepts_value_equal_to_current_usage(
    field,
    usage,
    quota_limits,
):
    schema = IscsiQuotaSchema(
        context={
            "usage": {
                "clients": 0,
                "data_size_gb": 0,
                "disks": 0,
                "snapshots": 0,
            }
            | {field: usage}
        },
        partial=True,
    )

    loaded = schema.load(make_update_quota_body(**{field: usage}))

    assert loaded[field] == usage
