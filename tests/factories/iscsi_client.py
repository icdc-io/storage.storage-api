import factory

from app.database import db
from app.models.iscsi_client import IscsiClients
from app.models.iscsi_disk import IscsiDisks
from tests.factories.base import BaseFactory, BasePayloadFactory


class IscsiClientFactory(BaseFactory):
    """Factory for creating iSCSI client database models.

    Generates realistic test data for iSCSI client objects with unique
    sequential values for names, IQNs, and credentials.
    """

    class Meta:
        model = IscsiClients

    name = factory.Sequence(lambda n: f"client-bbbb{n + 1000}")
    iqn = factory.Sequence(lambda n: f"iqn.2024-01.com.example:client{n:04d}")
    chap_username = factory.Sequence(lambda n: f"user{n + 1000}")
    chap_password = factory.Sequence(lambda n: f"password{n + 1000}")
    owner = factory.Sequence(lambda n: f"client_owner{n}@example.com")
    account_id: int


class IscsiClientPayload(BasePayloadFactory):
    """Factory for creating iSCSI client API payloads.

    Generates request payloads for client creation via API.
    Uses account_name instead of account_id for API compatibility.
    """

    name = factory.Sequence(lambda n: f"client-aaaa{n + 1000}")
    iqn = factory.Sequence(lambda n: f"iqn.2024-01.com.exampledict:client{n:04d}")
    chap_username = factory.Sequence(lambda n: f"user{n + 1000}")
    chap_password = factory.Sequence(lambda n: f"password{n + 1000}")
    owner = factory.Sequence(lambda n: f"owner_client{n}@example.com")
    account_name: str

    class Params:
        manual = factory.Trait(
            name=None,
            iqn=None,
            chap_username=None,
            chap_password=None,
            owner=None,
        )
        chap = factory.Trait(
            chap_username="testusername",
            chap_password="testpassword"
        )
        new_owner = factory.Trait(owner="new_owner@example.com")


class IscsiAssignedClientFactory(BaseFactory):
    """Factory for assigning iSCSI clients to disks.

    Provides methods to create client-disk associations either in database
    only or synchronized with Ceph storage.
    """

    client_id: int
    disk_id: int

    @classmethod
    def create(cls, client, disk):
        """Create client-disk assignment in database only.

        Args:
            client: IscsiClient object to assign disk to
            disk: IscsiDisk object to assign to client

        Returns:
            Client object with disk appended to disks list
        """
        client.disks.append(disk)
        db.session.commit()
        return client

    @classmethod
    def assign(cls, client, disk):
        """Create client-disk assignment synchronized to Ceph.

        Registers the assignment both in database and in Ceph storage
        via iSCSI service API.

        Args:
            client: IscsiClient object to assign disk to
            disk: IscsiDisk object to assign to client

        Returns:
            Client object with disk appended to disks list
        """
        iscsi_service = disk.target.iscsi_service()
        iscsi_service.assign_disk(client, disk.name)

        client.disks.append(disk)
        db.session.commit()
        return client


class IscsiAssignedClientPayload(BasePayloadFactory):
    """Factory for creating client assignment API payloads.

    Generates properly formatted disk assignment payloads for API requests.
    Accepts disk objects, IDs, or lists and converts them to API format.
    """

    disks: list[dict[id, int]]

    @classmethod
    def build(cls, disks):
        """Build API payload for disk assignment.

        Converts various disk input formats into standardized API payload.

        Args:
            disks: Single disk or list of disks (can be IscsiDisk objects or IDs)

        Returns:
            List of dicts in format [{"id": disk_id}, ...]
        """
        payload = []

        # Normalize to list format
        disk_list = disks if isinstance(disks, list) else [disks]

        # Convert each disk to payload format
        for disk in disk_list:
            if isinstance(disk, int):
                # Disk provided as ID
                payload.append({"id": disk})
            elif isinstance(disk, IscsiDisks):
                # Disk provided as model object
                payload.append({"id": disk.id})

        return payload
