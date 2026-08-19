import pytest

from app.database import db
from app.lib.request_utils import is_failed
from tests.builders.ceph_namespace import CephAccountEnv, CephIscsiEnv
from tests.support.package_setup import setup_integration_package


@pytest.fixture(scope="package", autouse=True)
def integration_package(make_connection):
    yield from setup_integration_package(make_connection)


@pytest.fixture
def env(integration_package) -> CephIscsiEnv:
    env = CephIscsiEnv(package=integration_package)
    try:
        yield env
    finally:
        env.cleanup()


@pytest.fixture
def assigned_ceph_factory(env):
    """Create a client with real Ceph disk assignments."""

    def factory(*, disk_pools="nvme", client_kwargs=None, disk_kwargs=None):
        client_kwargs = client_kwargs or {}
        disk_kwargs = disk_kwargs or {}
        pool_names = [disk_pools] if isinstance(disk_pools, str) else disk_pools

        client = env.client(**client_kwargs)
        disks = [
            env.disk(
                target=env.scope(pool_name=pool_name).target,
                **disk_kwargs,
            )
            for pool_name in pool_names
        ]
        env.assign(client=client, disks=disks)
        return client

    return factory


@pytest.fixture
def ceph_unassign_client():
    """Disconnect assigned disks from Ceph and mirror the relation in DB."""

    def unassign(client, disks=None):
        disks = list(disks or client.disks)

        for disk in disks:
            response = disk.target.iscsi_service().disconnect_disk(
                client.iqn,
                disk.name,
            )
            if is_failed(response):
                db.session.rollback()
                raise AssertionError(
                    f"Failed to unassign disk '{disk.name}' from client "
                    f"'{client.name}' in Ceph. Response: {response}"
                )

            if disk in client.disks:
                client.disks.remove(disk)

        db.session.commit()
        return client

    return unassign
