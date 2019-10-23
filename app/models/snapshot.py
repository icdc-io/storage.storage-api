"""
Snapshots model
"""
from sqlalchemy.sql import func

from app.database import db
from app.models.model import AbstractModel


class Snapshots(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    size_gb = db.Column(db.Integer)
    provisioned = db.Column(db.Integer)
    description = db.Column(db.String(128))
    creation_time = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    disk_id = db.Column(db.Integer, db.ForeignKey("iscsi_disks.id"))

    def __repr__(self):
        return f"Snapshots({self.id}, {self.name}, {self.size_gb}, \
            {self.description}, {self.creation_time}, {self.disk_id})"

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
            "name": "self.name",
            "size_gb": "self.size_gb",
            "description": "self.description",
            "creation_time": "self.creation_time",
            "disk_id": "self.disk_id",
        }
        return self.response_filter(fields, hide_params)

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.description = body.get("description", self.description)
        self.name = body.get("new_snapshot_name", self.name)
        self.save()
