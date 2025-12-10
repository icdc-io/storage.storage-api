import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_disk import IscsiDiskPayload
from tests.fixtures.iscsi_disk import verify_disk_size_gb
from tests.schemes import IscsiDiskResponseTestSchema


def validate_schema(body):
    try:
        IscsiDiskResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")


def test_member_can_update_own_disk(api, account, disk_db):
    """Member can update their own iSCSI disk."""
    payload = IscsiDiskPayload.build(size_gb=3)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=disk_db.owner,
    )

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 200
    validate_schema(body)


def test_member_cannot_update_non_own_disk(api, account, disk_db):
    """Member cannot update disk they do not own."""
    payload = IscsiDiskPayload.build(size_gb=3)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        fake_user=True,
    )

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 404, "Disk not found."


def test_member_cannot_change_owner_of_own_disk(api, account, disk_db):
    """Member cannot change owner of their own disk."""
    payload = IscsiDiskPayload.build(new_owner=True)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=disk_db.owner,
    )

    old_owner = disk_db.owner

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] == old_owner, "Owner must not change."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_update_account_disk(
    api,
    account,
    disk_db,
    role,
):
    """Admin/Owner can update disks in their own account."""
    payload = IscsiDiskPayload.build(size_gb=3)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 200
    validate_schema(body)


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_update_disk_in_other_account(
    api,
    account_factory,
    disk_db,
    role,
):
    """No non-operator role can update disk in another account."""
    account = account_factory()
    payload = IscsiDiskPayload.build(size_gb=3)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=disk_db.owner,
    )

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 404, "Disk not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_change_disk_owner(
    api,
    account,
    disk_db,
    role,
):
    """Admin/Owner can change disk owner."""
    payload = IscsiDiskPayload.build(new_owner=True)
    old_owner = disk_db.owner
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] != old_owner, "Owner must change."


def test_operator_can_update_disk_in_any_account(api, account, disk_db):
    """Operator can update any disk across accounts."""
    payload = IscsiDiskPayload.build(size_gb=3)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 200
    validate_schema(body)


def test_operator_can_change_disk_owner(api, account, disk_db):
    """Operator can change disk owner."""
    payload = IscsiDiskPayload.build(new_owner=True)
    headers = HeadersPayload.build(operator=True)
    old_owner = disk_db.owner

    status, body = api.iscsi.disks.update(disk_db.id, payload, headers)

    assert status == 200
    validate_schema(body)
    assert body["owner"] != old_owner, "Owner must change."


def test_update_nonexistent_disk_returns_404(api):
    """Updating nonexistent disk should return 404."""
    payload = IscsiDiskPayload.build()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(99999, payload, headers)

    assert status == 404, "Disk not found."


def test_disk_overload_size_gb_quota(
    api,
    iscsi_quota,
    target,
    disk_db_factory,
):
    """Updating disk size above quota must fail."""
    disk = disk_db_factory(
        target=target,
        size_gb=iscsi_quota.data_size_gb,
    )

    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=disk.size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk.id, payload, headers)

    assert status == 400
    assert disk.size_gb == iscsi_quota.data_size_gb


@pytest.mark.parametrize("disk_count", [2, 3, 6])
def test_disks_overload_size_gb_quota(
    api,
    account,
    target_factory,
    iscsi_quota_factory,
    disk_db_factory,
    disk_count,
):
    """Updating one of disks so that total exceeds quota must fail."""
    target = target_factory(account=account)
    quota = iscsi_quota_factory(
        account=account,
        big=True,
        data_size_gb=12,
    )
    size_gb = quota.data_size_gb / disk_count
    disks = disk_db_factory(
        target=target,
        count=disk_count,
        size_gb=size_gb,
    )

    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=disks[0].size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disks[0].id, payload, headers)

    assert status == 400
    assert disks[0].size_gb == size_gb


def test_disk_size_gb_quota(
    api,
    target,
    iscsi_quota,
    disk_db_factory,
):
    """Updating disk size up to quota must succeed."""
    disk = disk_db_factory(
        target=target,
        size_gb=iscsi_quota.data_size_gb - 1,
    )

    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=disk.size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk.id, payload, headers)

    assert status == 200
    assert disk.size_gb == iscsi_quota.data_size_gb


@pytest.mark.parametrize("disk_count", [2, 3, 6])
def test_disks_size_gb_quota(
    api,
    account,
    target_factory,
    iscsi_quota_factory,
    disk_db_factory,
    disk_count,
):
    """Updating disk size within total quota must succeed."""
    target = target_factory(account=account)
    quota = iscsi_quota_factory(
        account=account,
        big=True,
        data_size_gb=13,
    )
    size_gb = (quota.data_size_gb - 1) / disk_count
    disks = disk_db_factory(
        target=target,
        count=disk_count,
        size_gb=size_gb,
    )

    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=disks[0].size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disks[0].id, payload, headers)

    assert status == 200
    assert disks[0].size_gb == size_gb + 1


@pytest.mark.ceph
def test_disk_size_gb_update_ceph(api, disk_ceph):
    """Disk size change should be applied in Ceph."""
    size_gb = disk_ceph.size_gb
    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ceph.id, payload, headers)

    assert status == 200
    assert disk_ceph.size_gb == size_gb + 1
    assert verify_disk_size_gb(disk_ceph)


def test_disks_cannot_be_decreased(api, disk_ceph):
    """Decreasing disk size must be rejected."""
    size_gb = disk_ceph.size_gb
    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=size_gb - 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ceph.id, payload, headers)

    assert status == 400
    assert disk_ceph.size_gb == size_gb


def test_disks_when_size_gb_remains_same(api, disk_ceph):
    """Updating size to the same value should be a no-op."""
    size_gb = disk_ceph.size_gb
    payload = IscsiDiskPayload.build(
        manual=True,
        size_gb=size_gb,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ceph.id, payload, headers)

    assert status == 200
    assert disk_ceph.size_gb == size_gb
