"""
iSCSI Disk model
"""
from flask import abort
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)
from sqlalchemy import event

from app.database import db
from app.lib.request_utils import is_failed
from app.loggers import log
from app.models.iscsi_quota import IscsiQuotas
from app.models.model import AbstractModel
from app.models.relationships import iscsi_assigned_clients


class IscsiDisks(AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "iscsi.disks"
    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.String(128))
    size_gb = db.Column(db.Integer)
    name = db.Column(db.String(128))
    target_id = db.Column(db.Integer, db.ForeignKey("iscsi_targets.id"))

    target = db.relationship("IscsiTargets", back_populates="disks")
    clients = db.relationship(
        "IscsiClients",
        secondary=iscsi_assigned_clients,
        back_populates="disks",
        overlaps="client,clients"
    )
    snapshots = db.relationship(
        "Snapshots",
        back_populates="disk",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"IscsiDisks({self.id}, {self.owner}, {self.size_gb}, \
            {self.name}, {self.target_id}, {self.clients}, {self.snapshots})"

    def update(self, body):
        """UPDATE SET SQL"""
        self.size_gb = body.get("size_gb", self.size_gb)
        self.owner = body.get("owner", self.owner)
        self.save()

    @classmethod
    def related_objects(cls) -> list:
        from app.models.iscsi_target import IscsiTargets
        return [(IscsiTargets, cls.target_id)]

    @classmethod
    def schema(cls):
        return IscsiDiskSchema()

    @classmethod
    def to_dict_many(cls, disks):
        return IscsiDiskResponseSchema(many=True).dump(disks)

    @property
    def account_id(self):
        return self.target.account.id

    @property
    def pool_id(self):
        return self.target.pool_id

    def to_dict(self):
        """Serialize model"""
        return IscsiDiskResponseSchema().dump(self)

    def _snapshots(self):
        """Calculate snapshot statistics for this disk"""
        response = {"count": 0, "storage_gb": 0}
        for snapshot in self.snapshots:
            response["count"] += 1
            response["storage_gb"] += snapshot.size_gb
        return response

    def get_usage(self):
        """Return usage summary for quotas"""
        return {
            "data_size_gb": self.size_gb,
            "snapshots": len(self.snapshots),
            "disks": 1,
        }


class IscsiDiskSchema(Schema):
    DISK_NAME_PATTERN = r"^[a-z0-9._\-]+$"

    id = fields.Int(dump_only=True)
    owner = fields.String(validate=validate.Email(), required=True)
    size_gb = fields.Int(validate=validate.Range(min=1), required=True)
    name = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=24),
            validate.Regexp(regex=DISK_NAME_PATTERN)
        ),
        required=True
    )
    target_id = fields.Int(load_only=True, required=True)

    @validates_schema
    def validate_quota_exceeding(self, data, **kwargs):
        size_gb = data.get("size_gb")
        if size_gb is None:
            return

        disk = self.context.get("disk")
        quota = self.context.get("quota")

        if not quota and disk:
            quota = IscsiQuotas.query.filter_by(
                account_id=disk.account_id, pool_id=disk.pool_id
            ).first()
        if not quota:
            raise ValidationError("Quota for this pool not found.")

        usage = quota.compute_usage()
        delta = size_gb - (disk.size_gb if disk else 0)
        new_usage = usage["data_size_gb"] + delta

        if new_usage > quota.data_size_gb:
            raise ValidationError({
                "size_gb": [f"Requested disk size exceeds quota: {new_usage}/{quota.data_size_gb} GiB"]
            })
        elif delta == 0:
            del data["size_gb"]
        elif delta < 0:
            raise ValidationError({
                "size_gb": ["Resize disk must be higher than previous size."]
            })

        if not disk and usage["disks"] + 1 > quota.disks:
            raise ValidationError({
                "disks": [f"Disk limit reached: maximum allowed is {quota.disks}"]
            })


class IscsiDiskResponseSchema(IscsiDiskSchema):
    target = fields.Nested("IscsiTargetSchema", dump_only=True)
    clients = fields.Nested("IscsiClientSchema", dump_only=True, many=True)
    snapshots = fields.Nested("SnapshotSchema", dump_only=True, many=True)


def before_delete(mapper, connection, disk_instance):
    """
    Listener function called before deleting an IscsiDisks object.

    Disconnects the disk from all associated clients and deletes it from
    the iSCSI gateway if possible.
    """
    log.info(f"Deleting disk from cloud gateway (name={disk_instance.name}).")
    from app.models.iscsi_target import IscsiTargets
    target = IscsiTargets.get_by("id", disk_instance.target_id)
    if not target:
        log.warning(
            f"Target or gateways not found for disk (name={disk_instance.name}). "
            "Aborting deletion."
        )
        return
    try:
        iscsi_service = target.iscsi_service()
    except ValueError:
        return

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
