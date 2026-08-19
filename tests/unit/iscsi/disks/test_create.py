import pytest
from marshmallow import ValidationError

from app.models.iscsi_disk import IscsiDiskSchema
from tests.unit.iscsi.helpers import make_quota


def make_create_disk_body(**overrides):
    # This unit schema validates the internal disk shape with `target_id`.
    # The API payload factory uses `account_name` and `pool_id`, so a local
    # helper keeps this unit test aligned with the schema it exercises.
    body = {
        "owner": "user@example.com",
        "name": "disk01",
        "size_gb": 2,
        "target_id": 1,
    }
    body.update(overrides)
    return body


# Field validation


@pytest.mark.parametrize(
    "valid_owner",
    [
        "user@example.com",
        "test+tag@domain.org",
        "test_user@sub.domain.com",
    ],
)
def test_disk_schema_accepts_valid_owner_email(valid_owner):
    loaded = IscsiDiskSchema().load(make_create_disk_body(owner=valid_owner))

    assert loaded["owner"] == valid_owner


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
def test_disk_schema_rejects_invalid_owner_email(invalid_owner):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(make_create_disk_body(owner=invalid_owner))

    assert "owner" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_name",
    [
        "disk01",
        "disk-01",
        "disk.name_2",
        "a" * 24,
    ],
)
def test_disk_schema_accepts_valid_name(valid_name):
    loaded = IscsiDiskSchema().load(make_create_disk_body(name=valid_name))

    assert loaded["name"] == valid_name


@pytest.mark.parametrize(
    "invalid_name",
    [
        "disk bad",
        "disk!bad",
        "",
        None,
        "x" * 25,
    ],
)
def test_disk_schema_rejects_invalid_name(invalid_name):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(make_create_disk_body(name=invalid_name))

    assert "name" in exc_info.value.messages


@pytest.mark.parametrize("valid_size_gb", [1, 2, 10, 100])
def test_disk_schema_accepts_valid_size_gb(valid_size_gb):
    loaded = IscsiDiskSchema().load(make_create_disk_body(size_gb=valid_size_gb))

    assert loaded["size_gb"] == valid_size_gb


@pytest.mark.parametrize("invalid_size_gb", [0, -1, None])
def test_disk_schema_rejects_invalid_size_gb(invalid_size_gb):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(make_create_disk_body(size_gb=invalid_size_gb))

    assert "size_gb" in exc_info.value.messages


def test_disk_schema_rejects_invalid_size_gb_type():
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(make_create_disk_body(size_gb="bad"))

    assert "size_gb" in exc_info.value.messages


@pytest.mark.parametrize("valid_target_id", [1, 2, 999])
def test_disk_schema_accepts_valid_target_id(valid_target_id):
    loaded = IscsiDiskSchema().load(make_create_disk_body(target_id=valid_target_id))

    assert loaded["target_id"] == valid_target_id


@pytest.mark.parametrize("invalid_target_id", ["bad", None])
def test_disk_schema_rejects_invalid_target_id(invalid_target_id):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(make_create_disk_body(target_id=invalid_target_id))

    assert "target_id" in exc_info.value.messages


def test_disk_schema_accepts_string_target_id_with_current_coercion():
    loaded = IscsiDiskSchema().load(make_create_disk_body(target_id="1"))

    assert loaded["target_id"] == 1


@pytest.mark.parametrize("missing_field", ["owner", "name", "size_gb", "target_id"])
def test_disk_schema_rejects_missing_required_field(missing_field):
    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(make_create_disk_body(**{missing_field: None}))

    assert missing_field in exc_info.value.messages


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_disk_schema_rejects_unknown_field(unknown_field):
    payload = make_create_disk_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema().load(payload)

    assert unknown_field in exc_info.value.messages


# Quota validation


def test_disk_schema_accepts_create_without_quota_context():
    loaded = IscsiDiskSchema().load(make_create_disk_body(size_gb=2))

    assert loaded["size_gb"] == 2
    assert loaded["target_id"] == 1


@pytest.mark.parametrize(
    "quota_size_gb, usage_data_size_gb, requested_size_gb",
    [
        (31, 30, 2),
        (50, 48, 3),
        (25, 24, 2),
    ],
)
def test_disk_schema_rejects_size_gb_over_quota(
    quota_size_gb,
    usage_data_size_gb,
    requested_size_gb,
):
    quota = make_quota(
        data_size_gb=quota_size_gb,
        disks=999,
        usage_data_size_gb=usage_data_size_gb,
        usage_disks=1,
    )

    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(context={"quota": quota}).load(
            make_create_disk_body(size_gb=requested_size_gb)
        )

    assert "size_gb" in exc_info.value.messages


def test_disk_schema_accepts_size_gb_at_quota_boundary():
    quota = make_quota(
        data_size_gb=31,
        disks=999,
        usage_data_size_gb=29,
        usage_disks=1,
    )

    loaded = IscsiDiskSchema(context={"quota": quota}).load(
        make_create_disk_body(size_gb=2)
    )

    assert loaded["size_gb"] == 2


@pytest.mark.parametrize(
    "quota_size_gb, usage_data_size_gb, requested_size_gb",
    [
        (31, 29, 2),
        (50, 46, 4),
        (25, 23, 2),
    ],
)
def test_disk_schema_accepts_size_gb_within_quota(
    quota_size_gb,
    usage_data_size_gb,
    requested_size_gb,
):
    quota = make_quota(
        data_size_gb=quota_size_gb,
        disks=999,
        usage_data_size_gb=usage_data_size_gb,
        usage_disks=1,
    )

    loaded = IscsiDiskSchema(context={"quota": quota}).load(
        make_create_disk_body(size_gb=requested_size_gb)
    )

    assert loaded["size_gb"] == requested_size_gb


@pytest.mark.parametrize("quota_disks", [0, 3, 4])
def test_disk_schema_rejects_create_when_disk_count_quota_is_reached(quota_disks):
    quota = make_quota(
        data_size_gb=1000,
        disks=quota_disks,
        usage_data_size_gb=quota_disks,
        usage_disks=quota_disks,
    )

    with pytest.raises(ValidationError) as exc_info:
        IscsiDiskSchema(context={"quota": quota}).load(make_create_disk_body(size_gb=1))

    assert "disks" in exc_info.value.messages


def test_disk_schema_accepts_create_at_disk_count_quota_boundary():
    quota = make_quota(
        data_size_gb=1000,
        disks=3,
        usage_data_size_gb=2,
        usage_disks=2,
    )

    loaded = IscsiDiskSchema(context={"quota": quota}).load(
        make_create_disk_body(size_gb=1)
    )

    assert loaded["name"] == "disk01"
    assert loaded["size_gb"] == 1


@pytest.mark.parametrize("quota_disks", [1, 2, 3])
def test_disk_schema_accepts_create_within_disk_count_quota(quota_disks):
    quota = make_quota(
        data_size_gb=1000,
        disks=quota_disks,
        usage_data_size_gb=max(quota_disks - 1, 0),
        usage_disks=quota_disks - 1,
    )

    loaded = IscsiDiskSchema(context={"quota": quota}).load(
        make_create_disk_body(size_gb=1)
    )

    assert loaded["name"] == "disk01"
    assert loaded["size_gb"] == 1
