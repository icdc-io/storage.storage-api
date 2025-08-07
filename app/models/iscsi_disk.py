"""
iSCSI Disk model
"""
from flask import abort
from sqlalchemy import event
from marshmallow import (
    Schema,
    fields,
    validates_schema,
    ValidationError,
    validate,
)

from app.database import db
from app.lib.request_utils import is_failed
from app.loggers import log
from app.models.model import AbstractModel
from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_quota import IscsiQuotas
from app.models.relationships import iscsi_assigned_clients


class IscsiDisks(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """

    RESOURCE_NAME = "iscsi.disks"
    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.String(128))
    size_gb = db.Column(db.Integer)
    name = db.Column(db.String(128))
    config_id = db.Column(db.Integer, db.ForeignKey("iscsi_configs.id"))
    clients = db.relationship(
        "IscsiClients",
        secondary=iscsi_assigned_clients,
        back_populates="disks",
        overlaps="client,clients"
    )
    snapshots = db.relationship(
        "Snapshots", back_populates="disk", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"IscsiDisks({self.id}, {self.owner}, {self.size_gb}, \
            {self.name}, {self.config_id}, {self.clients}, {self.snapshots})"

    def save(self):
        """
        INSERT SQL
        """
        self._commit(db)

    def remove(self):
        """
        DELETE SQL
        """
        self._delete(db)

    def serialize(self, hide_params=None):
        """
        Serialize model method
        """
        super()._serialize()
        fields = {
            "id": "self.id",
            "owner": "self.owner",
            "size_gb": "self.size_gb",
            "name": "self.name",
            "config": "self.config_id",
            "clients": "self._clients()",
            "snapshots": "self._snapshots()",
        }
        return self.response_filter(fields, hide_params)

    def _clients(self):
        """
        Retrieves and serializes IscsiClients associated with the clients attribute.
        No parameters.
        Returns a list of serialized IscsiClients with specified attributes.
        """
        from app.models.iscsi_client import IscsiClients  # fix circular import

        return [
            IscsiClients.get_by("id", object.id).serialize(["disks", "account"])
            for object in self.clients
        ]

    def _snapshots(self):
        response = {"count": 0, "storage_gb": 0}
        for snapshot in self.snapshots:
            response["count"] += 1
            response["storage_gb"] += snapshot.size_gb

        return response

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.size_gb = body.get("size_gb", self.size_gb)
        self.owner = body.get("owner", self.owner)
        self.save()

    def get_usage(self):
        usage = {
            "data_size_gb": self.size_gb,
            "snapshots": len(self.snapshots),
            "disks": 1
        }
        return usage


class IscsiDiskSchema(Schema):
    DISK_NAME_PATTERN = r"^[a-z0-9._\-]+$"

    id = fields.Int(dump_only=True)
    owner = fields.String(validate=validate.Email())
    size_gb = fields.Int(validate=validate.Range(min=0))
    name = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=24),
            validate.Regexp(regex=DISK_NAME_PATTERN)
        )
    )
    config_id = fields.Int()
    clients = fields.Function(lambda disk: disk._clients(), dump_only=True)
    snapshots = fields.Function(lambda disk: disk._snapshots(), dump_only=True)

    @validates_schema
    def validate_quota_exceeding(self, data, **kwargs):
        size_gb = data.get("size_gb")
        if size_gb is None:
            return

        config = self.context.get("config")
        disk = self.context.get("disk")
        quota = self.context.get("quota")

        if not quota and config:
            quota = IscsiQuotas.query.filter_by(
                account_id=config.account_id, pool_id=config.pool_id
            ).first()

        if not quota:
            return

        usage = quota.compute_usage()
        delta = size_gb - (disk.size_gb if disk else 0)
        new_usage = usage["data_size_gb"] + delta

        if new_usage > quota.data_size_gb:
            raise ValidationError({
                "size_gb": [f"Requested disk size exceeds quota: {new_usage}/{quota.data_size_gb} GiB"]
            })
        elif delta <= 0:
            raise ValidationError({
                "size_gb": [f"Resize disk must be higher than previous size."]
            })

        if not disk and usage["disks"] + 1 > quota.disks:
            raise ValidationError({
                "disks": [f"Disk limit reached: maximum allowed is {quota.disks}"]
            })


def before_delete(mapper, connection, disk_instance):
    """
    Listener function called before deleting an IscsiDisks object.

    Disconnects the disk from all associated clients and deletes it from
    the iSCSI gateway if possible.
    """
    log.info(f"Deleting disk from cloud gateway (name={disk_instance.name}).")

    config = IscsiConfigs.get_by("id", disk_instance.config_id)
    if not config:
        log.warning(
            f"Config or gateways not found for disk (name={disk_instance.name}). "
            "Aborting deletion."
        )
        return

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    for client in disk_instance.clients:
        response = iscsi_service.disconnect_disk(client.iqn, disk_instance.name)
        if is_failed(response):
            log.error(
                f"Failed to disconnect disk for client '{client.name}' "
                f"(disk={disk_instance.name}): "
                f"{response['data']}"
            )
            abort(response["code"], response["data"])

    response = iscsi_service.delete_disk(disk_name=disk_instance.name)
    if is_failed(response):
        abort(response["code"], response["data"])

    log.info(f"Disk '{disk_instance.name}' deleted successfully.")


event.listen(IscsiDisks, "before_delete", before_delete)
