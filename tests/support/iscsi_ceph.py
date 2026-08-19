from app.lib.request_utils import is_failed
from app.loggers import log


def _normalize_ceph_image_name(image_name):
    return image_name.split("/")[-1].split("_", 1)[-1]


def verify_disk_assignment(client, disks):
    """Verify that disks are assigned to a client in Ceph."""
    disk_list = disks if isinstance(disks, list) else [disks]

    for disk in disk_list:
        iscsi_service = disk.target.iscsi_service()
        client_images = iscsi_service.get_client_disks(client.iqn)

        image_names = [
            _normalize_ceph_image_name(img)
            for img in client_images
        ]

        if disk.name not in image_names:
            log.error(
                "Disk assignment verification failed: "
                "client_iqn=%s disk=%s expected_image=%s target=%s "
                "raw_client_images=%s normalized_images=%s",
                client.iqn,
                disk.name,
                iscsi_service.get_image_name(disk.name),
                getattr(disk.target, "iqn", None),
                client_images,
                image_names,
            )
            return False

    return True


def verify_client_exists(client, pools=None):
    """Verify that a client exists in Ceph targets for the given pools."""
    pools = ["nvme"] if pools is None else pools
    pool_list = [pools] if isinstance(pools, str) else pools
    targets = {
        disk.target.pool.klass: disk.target
        for disk in client.disks
    }

    for pool in pool_list:
        target = targets.get(pool)
        if target is None:
            return False

        service = target.iscsi_service()
        response = service.get_client(client.iqn)

        if is_failed(response):
            return False

    return True


def verify_client_credentials(client):
    """Verify that CHAP credentials are updated in Ceph."""
    checked_targets = set()

    for disk in client.disks:
        target = disk.target

        if target.id in checked_targets:
            continue

        checked_targets.add(target.id)

        service = target.iscsi_service()
        info = service.get_client(client.iqn)
        auth = info.get("data", {}).get("auth", {})

        if (
            auth.get("password") != client.chap_password
            or auth.get("username") != client.chap_username
        ):
            return False

    return True


def verify_disk_size_gb(disk):
    """Verify that the resized disk still exists in Ceph."""
    iscsi_service = disk.target.iscsi_service()
    response = iscsi_service.get_disk(disk.name)
    return not is_failed(response)


def verify_disk_exists(disk):
    """Verify that the disk exists in the target service."""
    iscsi_service = disk.target.iscsi_service()
    response = iscsi_service.get_disk(disk.name)
    return not is_failed(response)


def verify_disk_absent(disk):
    """Verify that the disk no longer exists in the target service."""
    iscsi_service = disk.target.iscsi_service()
    response = iscsi_service.get_disk(disk.name)
    return is_failed(response)
