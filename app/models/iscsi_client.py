"""
iSCSI Client method
"""
from flask import abort
from sqlalchemy import event

from app.database import db
from app.lib.request_utils import is_failed, ok
from app.loggers import log
from app.models.iscsi_config import IscsiConfigs
from app.models.model import AbstractModel
from app.models.relationships import iscsi_assigned_clients
from app.models.iscsi_disk import IscsiDiskSchema



class IscsiClients(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "iscsi.clients"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    name = db.Column(db.String(128))
    chap_username = db.Column(db.String(128))
    chap_password = db.Column(db.String(128))
    iqn = db.Column(db.String(128), unique=True)
    owner = db.Column(db.String(128))
    disks = db.relationship(
        "IscsiDisks",
        secondary=iscsi_assigned_clients,
        back_populates="clients",
        overlaps="client,clients"
    )

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

    def __repr__(self):
        return f"IscsiClients({self.id}, {self.account_id}, {self.name}, {self.chap_username}, \
            {self.chap_password}, {self.owner}, {self.disks})"

    def serialize(self, hide_params=None):
        """
        Serialize model method
        """
        super()._serialize()
        fields = {
            "id": "self.id",
            "name": "self.name",
            "chap_username": "self.chap_username",
            "chap_password": "self.chap_password",
            "owner": "self.owner",
            "iqn": "self.iqn",
            "disks": "self._disks()",
        }
        return self.response_filter(fields, hide_params)

    def _disks(self):
        """
        Return a list of serialized IscsiDisks objects based on the "id" attribute, including "clients" and "config" fields.
        """
        from app.models.iscsi_disk import IscsiDisks

        return [
            IscsiDisks.get_by("id", object.id).serialize(["clients", "config"])
            for object in self.disks
        ]

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.chap_username = body.get("chap_username", self.chap_username)
        self.chap_password = body.get("chap_password", self.chap_password)
        self.owner = body.get("owner", self.owner)
        self.save()


from marshmallow import Schema, fields


class IscsiClientSchema(Schema):
    id = fields.Int(dump_only=True)
    account_id = fields.Int()
    name = fields.String()
    chap_username = fields.String()
    chap_password = fields.String()
    iqn = fields.String()
    owner = fields.String()
    disks = fields.Nested(IscsiDiskSchema(many=True, exclude=["snapshots", "clients"]), dump_only=True)


def before_delete(mapper, connection, client_instance):
    """
    Listener function, called before deleting an IscsiClients object.
    """
    configs = IscsiConfigs.query.filter_by(account_id=client_instance.account_id).all()

    for config in configs:
        try:
            iscsi_service = config.iscsi_service()
        except ValueError as e:
            log.warning(
                f"Skipping target '{config.target_iqn}' — {e}"
            )
            continue

        log.info(
            f"Attempting to delete client '{client_instance.name}' from target '{config.target_iqn}'"
        )

        response = iscsi_service.delete_client(client=client_instance)

        if is_failed(response):
            log.error(
                f"Failed to delete client '{client_instance.name}' from target '{config.target_iqn}': "
                f"{response['data']}"
            )
            abort(response["code"], response["data"])

        log.info(
            f"Client '{client_instance.name}' successfully deleted from target '{config.target_iqn}'"
        )


event.listen(IscsiClients, "before_delete", before_delete)
