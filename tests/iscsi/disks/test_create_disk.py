import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_disk import IscsiDiskPayload


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_operator_can_create_disk_in_any_pool(
    api,
    aqa,
    iscsi_pools,
    disk_cleaner,
    pool_name,
    role,
):
    """Operator header can create a disk for any pool."""
    pool = iscsi_pools[pool_name]

    payload = IscsiDiskPayload.build(
        pool_id=pool.id,
        account_name=aqa.name,
        size_gb=5,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)
    disk_cleaner(disk_ids=body["id"])

    assert status in (200, 201, 204), (
        f"Failed to create disk for pool {pool_name}"
    )


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
@pytest.mark.parametrize(
    "quota_size_gb, pre_create_disks, disks_size_gb",
    [
        (31, 3, 10),
        (50, 4, 12),
        (25, 2, 12),
        (15, 2, 7),
        (5, 1, 3),
    ],
)
def test_overload_of_iscsi_quota_by_size_gb(
    api,
    account,
    target_factory,
    iscsi_quota_factory,
    disk_db_factory,
    pool_name,
    quota_size_gb,
    pre_create_disks,
    disks_size_gb,
):
    """Creating disk that exceeds size quota must fail, but within quota must pass."""
    target = target_factory(account=account, target_pools=pool_name)
    quota = iscsi_quota_factory(
        account=account,
        quota_pools=pool_name,
        big=True,
        data_size_gb=quota_size_gb,
    )
    disk_db_factory(
        target=target,
        disk_pools=pool_name,
        count=pre_create_disks,
        size_gb=disks_size_gb,
    )

    size_gb = max(quota_size_gb - (pre_create_disks * disks_size_gb), 0)
    headers = HeadersPayload.build(operator=True)

    # 1) Переполнение квоты по размеру — ожидаем 400/409
    payload = IscsiDiskPayload.build(
        account_name=account.name,
        pool_id=quota.pool_id,
        size_gb=size_gb + 1,
    )
    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)
    assert status in (400, 409), (
        f"Expected quota error for pool {pool_name}, got {status}"
    )

    # 2) В пределах квоты — ожидаем успешное создание
    payload = IscsiDiskPayload.build(
        account_name=account.name,
        pool_id=quota.pool_id,
        size_gb=size_gb,
    )
    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)
    assert status in (200, 201), (
        f"Failed to create disk within size quota for pool {pool_name}"
    )


@pytest.mark.parametrize("quota_disks", [0, 3, 4])
def test_overload_of_iscsi_quota_by_disks_number(
    api,
    account,
    target_factory,
    iscsi_quota_factory,
    disk_db_factory,
    quota_disks,
):
    """Creating disk when disk-count quota is already reached must fail."""
    target = target_factory(account=account)
    quota = iscsi_quota_factory(
        account=account,
        disks=quota_disks,
        big=True,
    )
    disk_db_factory(
        target=target,
        count=quota_disks,
        size_gb=1,
    )
    headers = HeadersPayload.build(operator=True)

    payload = IscsiDiskPayload.build(
        account_name=account.name,
        pool_id=quota.pool_id,
        size_gb=1,
    )

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status in (400, 409), "Expected disk-count quota error"


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
@pytest.mark.parametrize(
    "quota_size_gb, pre_create_disks, disks_size_gb",
    [
        (30, 2, 10),
        (50, 3, 12),
        (25, 1, 12),
        (15, 1, 7),
        (5, 0, 3),
    ],
)
def test_create_within_iscsi_quota_by_size_gb(
    api,
    account,
    target_factory,
    iscsi_quota_factory,
    disk_db_factory,
    pool_name,
    quota_size_gb,
    pre_create_disks,
    disks_size_gb,
):
    """Creating disk within size quota must succeed."""
    target = target_factory(account=account, target_pools=pool_name)
    quota = iscsi_quota_factory(
        account=account,
        quota_pools=[pool_name],
        data_size_gb=quota_size_gb,
        big=True,
    )
    disk_db_factory(
        target=target,
        disk_pools=pool_name,
        count=pre_create_disks,
        size_gb=disks_size_gb,
    )

    size_gb = max(quota_size_gb - (pre_create_disks * disks_size_gb), 0)
    headers = HeadersPayload.build(operator=True)

    payload = IscsiDiskPayload.build(
        account_name=account.name,
        pool_id=quota.pool_id,
        size_gb=size_gb,
    )

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status in (200, 201), (
        f"Failed to create disk within quota for pool {pool_name}"
    )


@pytest.mark.parametrize("quota_disks", [1, 2, 3])
def test_create_within_iscsi_quota_by_disks_number(
    api,
    account,
    target_factory,
    iscsi_quota_factory,
    disk_db_factory,
    quota_disks,
):
    """Creating disk while disk-count quota is not reached must succeed."""
    target = target_factory(account=account)
    quota = iscsi_quota_factory(
        account=account,
        disks=quota_disks,
        big=True,
    )
    disk_db_factory(
        target=target,
        count=quota_disks - 1,
        size_gb=1,
    )
    headers = HeadersPayload.build(operator=True)

    payload = IscsiDiskPayload.build(
        account_name=account.name,
        pool_id=quota.pool_id,
        size_gb=1,
    )

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status in (200, 201), (
        "Failed to create disk within disk-number quota"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"owner": "user@example.com", "size_gb": 10, "name": "disk01"},
        {"owner": "admin@domain.io", "size_gb": 1, "name": "d_1"},
    ],
)
def test_create_disk_valid_payload(
    api,
    payload,
    account,
    target,
    iscsi_quota,
):
    """Valid payload should create disk successfully."""
    payload["pool_id"] = iscsi_quota.pool_id
    payload["account_name"] = account.name
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status in (200, 201)
    assert "id" in body


@pytest.mark.parametrize("missed_field", ["owner", "size_gb", "name", None])
def test_create_disk_missing_required_fields(
    api,
    missed_field,
    account,
    iscsi_quota,
    target,
):
    """Missing required fields should fail with 400."""
    kwargs = {}
    if missed_field:
        kwargs["min"] = True
        kwargs[missed_field] = None

    payload = IscsiDiskPayload.create(**kwargs)
    payload["pool_id"] = iscsi_quota.pool_id
    payload["account_name"] = account.name
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status == 400
    assert any(
        k in str(body).lower()
        for k in ["missing", "required", "invalid"]
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"owner": "invalid_email", "size_gb": 10, "name": "disk01"},
        {"owner": "user@example.com", "size_gb": -1, "name": "disk01"},
        {"owner": "user@example.com", "size_gb": 10, "name": ""},
        {"owner": "user@example.com", "size_gb": 10, "name": "disk!bad"},
        {"owner": "user@example.com", "size_gb": 10, "name": "x" * 25},
    ],
)
def test_create_disk_invalid_values(
    api,
    payload,
    account,
    iscsi_quota,
    target,
):
    """Invalid field values should fail validation."""
    payload["pool_id"] = iscsi_quota.pool_id
    payload["account_name"] = account.name
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status == 400
    assert any(
        k in str(body).lower()
        for k in ["invalid", "not valid", "must be", "too long"]
    )


@pytest.mark.parametrize("extra_field", ["extra_field", "unrelated", "random_key"])
def test_create_disk_with_unknown_field(
    api,
    extra_field,
    account,
    target,
    iscsi_quota,
):
    """Unknown fields should be rejected."""
    kwargs = {"default": True}
    if extra_field:
        kwargs[extra_field] = "error"

    headers = HeadersPayload.build(operator=True)
    payload = IscsiDiskPayload.create(
        account_name=account.name,
        pool_id=iscsi_quota.pool_id,
        **kwargs,
    )

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status == 400
    assert extra_field in str(body)


def test_create_disk_no_quota_for_pool(
    api,
    account,
    target_factory,
):
    """Creating disk without quota for pool should return 404."""
    target = target_factory(account=account)
    payload = IscsiDiskPayload.create(
        min=True,
        pool_id=target.pool_id,
        account_name=account.name,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status == 404


def test_create_disk_no_target_for_pool(
    api,
    account,
    iscsi_quota,
):
    """Creating disk without target for pool should return 404."""
    payload = IscsiDiskPayload.create(
        min=True,
        pool_id=iscsi_quota.pool_id,
        account_name=account.name,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status == 404


def test_create_disk_with_size_0(
    api,
    aqa,
    iscsi_pool,
):
    """Creating disk with size_gb=0 should fail."""
    payload = IscsiDiskPayload.build(
        pool_id=iscsi_pool.id,
        size_gb=0,
    )
    headers = HeadersPayload.build(aqa_owner=True)

    status, body = api.iscsi.disks.create(payload=payload, hdr=headers)

    assert status in (400, 409), "Successfully created disk with size 0"
