"""
iSCSI Disk model
"""
from app.database import db
from app.models.model import AbstractModel
from app.models.iscsi_config import IscsiConfigs, IscsiConfigSchema
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
        backref="client",
        overlaps="client,clients",
    )
    snapshots = db.relationship(
        "Snapshots", backref="snapshots", cascade="all, delete-orphan"
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


from marshmallow import Schema, fields, validates_schema, ValidationError, pre_load
from app import consts


class IscsiDiskSchema(Schema):
    id = fields.Int(dump_only=True)
    owner = fields.String()
    size_gb = fields.Int()
    name = fields.String()
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

        if not disk and usage["disks"] + 1 > quota.disk_limit:
            raise ValidationError({
                "disks": [f"Disk limit reached: maximum allowed is {quota.disk_limit}"]
            })

