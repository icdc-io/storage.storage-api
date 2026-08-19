import pytest
from marshmallow import ValidationError

import app.models.iscsi_disk as iscsi_disk_model
from app.models.iscsi_disk import IscsiDiskSchema
from tests.unit.iscsi.helpers import make_disk, make_quota


def make_update_disk_body(**overrides):
    body = {
        "owner": "user@example.com",
        "size_gb": 3,
    }
    body.update(overrides)
    return body


def make_update_schema(*, current_size_gb, quota_size_gb, usage_data_size_gb):
    disk = make_disk(size_gb=current_size_gb)
    quota = make_quota(
        data_size_gb=quota_size_gb,
        usage_data_size_gb=usage_data_size_gb,
    )
    schema = IscsiDiskSchema(
        context={"disk": disk, "quota": quota},
        partial=True,
    )
    return schema, disk


# Field validation


@pytest.mark.parametrize(
    "valid_owner",
    [
        "user@example.com",
        "test+tag@domain.org",
        "test_user@sub.domain.com",
    ],
)
def test_update_disk_schema_accepts_valid_owner_email(valid_owner):
    loaded = IscsiDiskSchema(partial=True).load(
        make_update_disk_body(owner=valid_owner)
    )

    assert loaded["owner"] == valid_owner


def test_update_disk_schema_accepts_owner_only_payload():
    loaded = IscsiDiskSchema(partial=True).load(
        {"owner": "owner_only@example.com"}
    )

    assert loaded == {"owner": "owner_only@example.com"}


@pytest.mark.parametrize(
    "invalid_owner",
    [
        "user",
        "user@",
        "@example.com",
        "user@domain",
        "",
        None,
    ],
)
def test_update_disk_schema_rejects_invalid_owner_email(invalid_owner):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(partial=True).load(
            make_update_disk_body(owner=invalid_owner)
        )

    assert "owner" in exc_info.value.messages


@pytest.mark.parametrize("valid_size_gb", [1, 2, 10, 100])
def test_update_disk_schema_accepts_valid_size_gb(valid_size_gb):
    loaded = IscsiDiskSchema(partial=True).load(
        make_update_disk_body(size_gb=valid_size_gb)
    )

    assert loaded["size_gb"] == valid_size_gb


@pytest.mark.parametrize("invalid_size_gb", [0, -1, None])
def test_update_disk_schema_rejects_invalid_size_gb(invalid_size_gb):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(partial=True).load(
            make_update_disk_body(size_gb=invalid_size_gb)
        )

    assert "size_gb" in exc_info.value.messages


def test_update_disk_schema_rejects_invalid_size_gb_type():
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(partial=True).load(
            make_update_disk_body(size_gb="bad")
        )

    assert "size_gb" in exc_info.value.messages


def test_update_disk_schema_accepts_empty_payload():
    loaded = IscsiDiskSchema(partial=True).load({})

    assert loaded == {}


def test_update_disk_schema_accepts_valid_owner_and_size_gb_together():
    loaded = IscsiDiskSchema(partial=True).load(
        make_update_disk_body(
            owner="mixed@example.com",
            size_gb=5,
        )
    )

    assert loaded == {
        "owner": "mixed@example.com",
        "size_gb": 5,
    }


def test_update_disk_schema_rejects_invalid_mixed_payload():
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(partial=True).load(
            make_update_disk_body(
                owner="mixed@example.com",
                size_gb=0,
            )
        )

    assert "size_gb" in exc_info.value.messages


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_update_disk_schema_rejects_unknown_field(unknown_field):
    payload = make_update_disk_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(partial=True).load(payload)

    assert unknown_field in exc_info.value.messages


# Quota validation


def test_update_disk_schema_accepts_without_quota_context():
    loaded = IscsiDiskSchema(partial=True).load(make_update_disk_body(size_gb=3))

    assert loaded["size_gb"] == 3


def test_update_disk_schema_accepts_owner_only_with_quota_context():
    schema, _disk = make_update_schema(
        current_size_gb=2,
        quota_size_gb=10,
        usage_data_size_gb=2,
    )

    loaded = schema.load({"owner": "quota-owner@example.com"})

    assert loaded == {"owner": "quota-owner@example.com"}


def test_update_disk_schema_removes_size_when_new_value_matches_current_size():
    schema, _disk = make_update_schema(
        current_size_gb=2,
        quota_size_gb=10,
        usage_data_size_gb=2,
    )

    loaded = schema.load({"size_gb": 2})

    assert loaded == {}


def test_update_disk_schema_accepts_size_gb_at_quota_boundary():
    schema, _disk = make_update_schema(
        current_size_gb=19,
        quota_size_gb=20,
        usage_data_size_gb=19,
    )

    loaded = schema.load({"size_gb": 20})

    assert loaded == {"size_gb": 20}


def test_update_disk_schema_uses_quota_lookup_when_disk_context_has_no_quota(monkeypatch):
    disk = make_disk(size_gb=2)
    quota = make_quota(data_size_gb=10, usage_data_size_gb=2)

    quota_query = type("QuotaQuery", (), {})()
    quota_query.first = lambda: quota

    query = type("Query", (), {})()
    query.filter_by = lambda **_kwargs: quota_query

    fake_quotas = type("FakeQuotas", (), {"query": query})
    monkeypatch.setattr(iscsi_disk_model, "IscsiQuotas", fake_quotas)

    loaded = IscsiDiskSchema(
        context={"disk": disk},
        partial=True,
    ).load({"size_gb": 3})

    assert loaded == {"size_gb": 3}


def test_update_disk_schema_rejects_when_disk_quota_lookup_fails(monkeypatch):
    disk = make_disk(size_gb=2)

    quota_query = type("QuotaQuery", (), {})()
    quota_query.first = lambda: None

    query = type("Query", (), {})()
    query.filter_by = lambda **_kwargs: quota_query

    fake_quotas = type("FakeQuotas", (), {"query": query})
    monkeypatch.setattr(iscsi_disk_model, "IscsiQuotas", fake_quotas)

    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(
            context={"disk": disk},
            partial=True,
        ).load({"size_gb": 3})

    assert exc_info.value.messages == {"_schema": ["Quota for this pool not found."]}


@pytest.mark.parametrize(
    "current_size_gb, quota_size_gb, usage_data_size_gb, requested_size_gb",
    [
        (2, 10, 7, 3),
        (4, 20, 15, 5),
        (10, 50, 41, 19),
    ],
)
def test_update_disk_schema_accepts_resize_within_total_quota(
    current_size_gb,
    quota_size_gb,
    usage_data_size_gb,
    requested_size_gb,
):
    schema, _disk = make_update_schema(
        current_size_gb=current_size_gb,
        quota_size_gb=quota_size_gb,
        usage_data_size_gb=usage_data_size_gb,
    )

    loaded = schema.load({"size_gb": requested_size_gb})

    assert loaded == {"size_gb": requested_size_gb}


def test_update_disk_schema_rejects_resize_above_total_quota():
    schema, _disk = make_update_schema(
        current_size_gb=4,
        quota_size_gb=5,
        usage_data_size_gb=4,
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"size_gb": 6})

    assert "size_gb" in exc_info.value.messages


def test_update_disk_schema_rejects_decreasing_size():
    schema, _disk = make_update_schema(
        current_size_gb=4,
        quota_size_gb=10,
        usage_data_size_gb=4,
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"size_gb": 3})

    assert "size_gb" in exc_info.value.messages


def test_update_disk_schema_rejects_resize_when_quota_is_fully_used():
    schema, _disk = make_update_schema(
        current_size_gb=20,
        quota_size_gb=20,
        usage_data_size_gb=20,
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"size_gb": 21})

    assert "size_gb" in exc_info.value.messages


@pytest.mark.parametrize(
    "current_size_gb, quota_size_gb, usage_data_size_gb, requested_size_gb",
    [
        (4, 12, 12, 5),
        (3, 9, 9, 4),
        (2, 6, 6, 3),
    ],
)
def test_update_disk_schema_rejects_resize_when_multiple_disks_overflow_quota(
    current_size_gb,
    quota_size_gb,
    usage_data_size_gb,
    requested_size_gb,
):
    schema, _disk = make_update_schema(
        current_size_gb=current_size_gb,
        quota_size_gb=quota_size_gb,
        usage_data_size_gb=usage_data_size_gb,
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"size_gb": requested_size_gb})

    assert "size_gb" in exc_info.value.messages
