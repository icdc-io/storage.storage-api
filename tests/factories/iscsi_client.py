import factory

from app.models.iscsi_client import IscsiClients
from tests.factories.base import BaseFactory, BasePayloadFactory


class IscsiClientFactory(BaseFactory):
    class Meta:
        model = IscsiClients

    name = factory.Sequence(lambda n: f"client-db-{n + 1000}")
    iqn = factory.Sequence(lambda n: f"iqn.2024-01.com.example:clientdb{n:04d}")
    chap_username = factory.Sequence(lambda n: f"dbuser{n + 1000}")
    chap_password = factory.Sequence(lambda n: f"dbpassword{n + 1000}")
    owner = factory.Sequence(lambda n: f"client_db_owner{n}@example.com")
    account_id: int


class IscsiClientPayload(BasePayloadFactory):
    name = factory.Sequence(lambda n: f"client-api-{n + 1000}")
    iqn = factory.Sequence(lambda n: f"iqn.2024-01.com.example:clientapi{n:04d}")
    chap_username = factory.Sequence(lambda n: f"apiuser{n + 1000}")
    chap_password = factory.Sequence(lambda n: f"apipassword{n + 1000}")
    owner = factory.Sequence(lambda n: f"owner_client{n}@example.com")
    account_name = None

    class Params:
        updated_credentials = factory.Trait(
            chap_username="updateduser",
            chap_password="updated_pass",
        )
        changed_owner = factory.Trait(owner="updated_owner@example.com")


class IscsiAssignedClientPayload(BasePayloadFactory):
    disks: list[dict[str, int]]

    @classmethod
    def build(cls, disks):
        payload = []
        disk_list = disks if isinstance(disks, list) else [disks]

        for disk in disk_list:
            if isinstance(disk, int):
                payload.append({"id": disk})
            elif hasattr(disk, "id"):
                payload.append({"id": disk.id})

        return payload
