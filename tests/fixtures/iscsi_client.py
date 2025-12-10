import pytest

from app.lib.request_utils import is_failed
from app.models.iscsi_client import IscsiClients
from tests.factories.iscsi_client import (
    IscsiAssignedClientFactory,
    IscsiClientFactory,
)
from tests.fixtures.iscsi_target import aqa_targets


@pytest.fixture(scope="function")
def client(account, iscsi_quota):
    """Create a single iSCSI client for the given account."""
    return IscsiClientFactory.create(account_id=account.id)


@pytest.fixture(scope="function")
def aqa_client(aqa, client_cleaner):
    """Create a single iSCSI client for the AQA account."""
    client = IscsiClientFactory.create(account_id=aqa.id)
    client_cleaner(client)
    yield client


@pytest.fixture
def client_db_factory(account_factory):
    """Factory to create iSCSI clients for accounts."""

    def _create_clients(account=None, count=1, **kwargs):
        if not account:
            account = account_factory()

        clients = [
            IscsiClientFactory.create(account_id=account.id, **kwargs)
            for _ in range(count)
        ]
        return clients[0] if count == 1 else clients

    return _create_clients


@pytest.fixture
def client_factory(aqa, client_cleaner):
    """Factory to create iSCSI clients for account AQA."""

    def _create_clients(count=1, **kwargs):
        clients = [
            IscsiClientFactory.create(account_id=aqa.id, **kwargs)
            for _ in range(count)
        ]
        for c in clients:
            client_cleaner(c)
        return clients[0] if count == 1 else clients

    return _create_clients


@pytest.fixture
def client_db_assigned(client, disk_db):
    """Create a client with assigned disk in database only (no Ceph sync)."""
    return IscsiAssignedClientFactory.create(client, disk_db)


@pytest.fixture
def assigned_db_factory(disk_db_factory, client_factory):
    """Factory to create clients with assigned disks in database only."""

    def _create_assigned_client(
        clients=None,
        disks=None,
        disk_pools="nvme",
        client_count=1,
        disk_count=1,
        **kwargs,
    ):
        if not disks:
            disks = disk_db_factory(
                disk_pools=disk_pools,
                count=disk_count,
                **kwargs,
            )

        disk_list = disks if isinstance(disks, list) else [disks]

        if not clients:
            account = disk_list[0].target.account
            clients = client_factory(
                account=account,
                count=client_count,
                **kwargs,
            )

        client_list = clients if isinstance(clients, list) else [clients]

        for c in client_list:
            for disk in disk_list:
                IscsiAssignedClientFactory.create(c, disk)

        return client_list[0] if client_count == 1 else client_list

    return _create_assigned_client


@pytest.fixture
def client_ceph_assigned(aqa_client, disk_ceph):
    """Create a client with assigned disk synchronized to Ceph."""
    return IscsiAssignedClientFactory.assign(aqa_client, disk_ceph)


@pytest.fixture
def assigned_ceph_factory(client_factory, disk_ceph_factory):
    """Factory to create clients with disks synced to Ceph."""

    def _create_synced_client(
        clients=None,
        disks=None,
        disk_pools="nvme",
        client_count=1,
        disk_count=1,
        **kwargs,
    ):
        if not disks:
            disks = disk_ceph_factory(
                disk_pools=disk_pools,
                count=disk_count,
            )

        disk_list = disks if isinstance(disks, list) else [disks]

        if not clients:
            clients = client_factory(
                count=client_count,
                **kwargs,
            )

        client_list = clients if isinstance(clients, list) else [clients]

        for c in client_list:
            for disk in disk_list:
                IscsiAssignedClientFactory.assign(c, disk)

        return client_list[0] if client_count == 1 else client_list

    return _create_synced_client


@pytest.fixture
def client_cleaner(cleaner):
    """Fixture to delete clients from database and optionally from Ceph."""

    def _delete_clients(clients=None, client_ids=None, immediate=False):
        cleaner.delete(
            IscsiClients,
            objects=clients,
            ids=client_ids,
            immediate=immediate,
        )

    return _delete_clients


@pytest.fixture
def ceph_unassign_client():
    """Unassign disks from iSCSI client in Ceph."""

    def _unassign(client, disks=None):
        disks = disks or client.disks
        disk_list = disks if isinstance(disks, list) else [disks]

        for disk in disk_list:
            iscsi_service = disk.target.iscsi_service()
            iscsi_service.disconnect_disk(client.iqn, disk.name)

            if disk in client.disks:
                client.disks.remove(disk)

    return _unassign


@pytest.fixture
def db_unassign_client():
    """Unassign disks from iSCSI client in database only."""

    def _unassign(client, disks=None):
        disks = disks or client.disks
        disk_list = disks if isinstance(disks, list) else [disks]

        for disk in disk_list:
            if disk in client.disks:
                client.disks.remove(disk)

    return _unassign


def verify_disk_assignment(client, disks):
    """Verify that disks are assigned to a client in Ceph."""
    disk_list = disks if isinstance(disks, list) else [disks]

    for disk in disk_list:
        iscsi_service = disk.target.iscsi_service()
        client_images = iscsi_service.get_client_disks(client.iqn)

        image_names = [
            img.split("/")[-1].split("_", 1)[-1]
            for img in client_images
        ]

        if disk.name not in image_names:
            return False

    return True


def verify_client_exists(client, pools=None):
    """Verify that a client exists in Ceph targets for given pools."""
    pools = ["nvme"] if pools is None else pools
    pool_list = [pools] if isinstance(pools, str) else pools

    targets = aqa_targets(client.account)

    for pool in pool_list:
        target = targets[pool]
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
