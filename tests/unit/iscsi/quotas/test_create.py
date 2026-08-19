from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema


def make_create_quota_body(**overrides):
    body = {
        "clients": 4,
        "data_size_gb": 20,
        "disks": 10,
        "snapshots": 6,
        "account_id": 1,
        "pool_id": 1,
    }
    body.update(overrides)
    return body


def make_limitset(*, clients=10, data_size_gb=100, disks=20, snapshots=30):
    return SimpleNamespace(
        clients=clients,
        data_size_gb=data_size_gb,
        disks=disks,
        snapshots=snapshots,
    )


@pytest.fixture
def quota_limits(monkeypatch):
    monkeypatch.setattr(
        IscsiQuotaSchema,
        "_IscsiQuotaSchema__get_pool",
        lambda self, pool_id: SimpleNamespace(id=pool_id),
    )
    monkeypatch.setattr(
        IscsiQuotas,
        "get_pool_limitset",
        classmethod(lambda cls, pool_id: make_limitset()),
    )


# Field validation


@pytest.mark.parametrize("field", ["clients", "data_size_gb", "disks", "snapshots"])
def test_iscsi_quota_schema_accepts_valid_quota_field(field, quota_limits):
    loaded = IscsiQuotaSchema().load(make_create_quota_body(**{field: 1}))

    assert loaded[field] == 1


@pytest.mark.parametrize("field", ["clients", "data_size_gb", "disks", "snapshots"])
@pytest.mark.parametrize("value", [-1, "bad", None])
def test_iscsi_quota_schema_rejects_invalid_quota_field(field, value, quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema().load(make_create_quota_body(**{field: value}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize("field", ["account_id", "pool_id"])
def test_iscsi_quota_schema_accepts_valid_id_field(field, quota_limits):
    loaded = IscsiQuotaSchema().load(make_create_quota_body(**{field: 2}))

    assert loaded[field] == 2


@pytest.mark.parametrize("field", ["account_id", "pool_id"])
@pytest.mark.parametrize("value", ["bad", None])
def test_iscsi_quota_schema_rejects_invalid_id_field(field, value, quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema().load(make_create_quota_body(**{field: value}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "missing_field",
    ["clients", "data_size_gb", "disks", "snapshots", "account_id", "pool_id"],
)
def test_iscsi_quota_schema_rejects_missing_required_field(missing_field, quota_limits):
    body = make_create_quota_body()
    body.pop(missing_field)

    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema().load(body)

    assert missing_field in exc_info.value.messages


def test_iscsi_quota_schema_rejects_extra_field(quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema().load(make_create_quota_body(extra_field="nope"))

    assert "extra_field" in exc_info.value.messages


def test_iscsi_quota_schema_rejects_unknown_pool(monkeypatch):
    monkeypatch.setattr(
        IscsiQuotaSchema,
        "_IscsiQuotaSchema__get_pool",
        lambda self, pool_id: (_ for _ in ()).throw(ValidationError("Must exist.", "pool")),
    )

    with pytest.raises(ValidationError) as exc_info:
        IscsiQuotaSchema().load(make_create_quota_body(pool_id=999))

    assert "Must exist." in str(exc_info.value.messages)


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
def test_iscsi_quota_schema_rejects_value_over_pool_limit(
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
        IscsiQuotaSchema().load(make_create_quota_body(**{field: requested}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "field, limit",
    [
        ("clients", 10),
        ("data_size_gb", 100),
        ("disks", 20),
        ("snapshots", 30),
    ],
)
def test_iscsi_quota_schema_accepts_value_at_pool_limit(
    field,
    limit,
    monkeypatch,
    quota_limits,
):
    monkeypatch.setattr(
        IscsiQuotas,
        "get_pool_limitset",
        classmethod(lambda cls, pool_id: make_limitset(**{field: limit})),
    )

    loaded = IscsiQuotaSchema().load(make_create_quota_body(**{field: limit}))

    assert loaded[field] == limit


@pytest.mark.parametrize(
    "field, usage, requested",
    [
        ("clients", 4, 3),
        ("data_size_gb", 12, 11),
        ("disks", 7, 6),
        ("snapshots", 5, 4),
    ],
)
def test_iscsi_quota_schema_rejects_value_below_current_usage(
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
        }
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_create_quota_body(**{field: requested}))

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
def test_iscsi_quota_schema_accepts_value_equal_to_current_usage(
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
        }
    )

    loaded = schema.load(make_create_quota_body(**{field: usage}))

    assert loaded[field] == usage
