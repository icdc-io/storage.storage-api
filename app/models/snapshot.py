"""
Snapshots model
"""
from flask import abort
from marshmallow import Schema, fields, validate
from sqlalchemy import event
from sqlalchemy.sql import func

from app.database import db
from app.lib.request_utils import is_failed
from app.loggers import log
from app.models.iscsi_disk import IscsiDisks
from app.models.model import AbstractModel


class Snapshots(AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "iscsi.snapshots"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    size_gb = db.Column(db.Integer)
    provisioned = db.Column(db.Integer)
    description = db.Column(db.String(128))
    creation_time = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    disk_id = db.Column(db.Integer, db.ForeignKey("iscsi_disks.id"))
    disk = db.relationship("IscsiDisks", back_populates="snapshots")

    def __repr__(self):
        return f"Snapshots({self.id}, {self.name}, {self.size_gb}, \
            {self.description}, {self.creation_time}, {self.disk_id})"

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.description = body.get("description", self.description)
        self.name = body.get("name", self.name)
        self.save()

    @classmethod
    def related_objects(cls) -> list:
        from app.models.iscsi_disk import IscsiDisks
        return [(IscsiDisks, cls.disk_id)]

    @property
    def target(self):
        return self.disk.target

    @classmethod
    def schema(cls):
        return SnapshotSchema()

    @classmethod
    def to_dict_many(cls, snapshots):
        return SnapshotResponseSchema(many=True).dump(snapshots)

    def to_dict(self):
        """
        Serialize model method
        """
        return SnapshotResponseSchema().dump(self)


class SnapshotSchema(Schema):
    SNAPSHOT_NAME_PATTERN = r'^[a-z0-9_.\-]+$'
    SNAPSHOT_DESCRIPTION_PATTERN = r"^[\w ,.:/;\[\]!@^*()_\-+=]*$"

    id = fields.Int(dump_only=True)
    name = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=32),
            validate.Regexp(regex=SNAPSHOT_NAME_PATTERN)
        )
    )
    description = fields.String(
        validate=validate.And(
            validate.Length(min=0, max=64),
            validate.Regexp(regex=SNAPSHOT_DESCRIPTION_PATTERN)
        )
    )
    provisioned = fields.Int()
    size_gb = fields.Int(dump_only=True)
    creation_time = fields.DateTime(dump_only=True)
    disk_id = fields.Int()


class SnapshotResponseSchema(SnapshotSchema):
    disk = fields.Nested("IscsiDiskSchema", dump_only=True)


def before_delete(mapper, connection, snapshot_instance):
    """
    Listener function, called before deleting a Snapshots object.
    """
    log.info(f"Deleting snapshot in RBD with name: {snapshot_instance.name}")
    from app.models.iscsi_target import IscsiTargets
    target = IscsiTargets.get_by("id", snapshot_instance.target.id)

    try:
        iscsi_service = target.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    disk = IscsiDisks.get_by("id", snapshot_instance.disk_id)

    response = iscsi_service.delete_snapshot(snapshot_name=snapshot_instance.name, disk_name=disk.name)
    if is_failed(response) and response["code"] != 404:
        abort(response["code"], response["data"])

    log.info(f"Snapshot '{snapshot_instance.name}' deleted successfully.")


event.listen(Snapshots, "before_delete", before_delete)
