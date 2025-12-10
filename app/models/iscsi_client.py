"""
iSCSI Client method
"""
from flask import abort
from marshmallow import Schema, fields, validate
from sqlalchemy import event

from app.database import db
from app.lib.request_utils import is_failed
from app.loggers import log
from app.models.model import AbstractModel
from app.models.relationships import iscsi_assigned_clients


class IscsiClients(AbstractModel):
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
    account = db.relationship(
        "Accounts",
        backref="clients"
    )
    disks = db.relationship(
        "IscsiDisks",
        secondary=iscsi_assigned_clients,
        back_populates="clients",
        overlaps="client,clients"
    )

    def __repr__(self):
        return f"IscsiClients({self.id}, {self.account_id}, {self.name}, {self.chap_username}, \
            {self.chap_password}, {self.owner}, {self.disks})"

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.name = body.get("name", self.name)
        self.chap_username = body.get("chap_username", self.chap_username)
        self.chap_password = body.get("chap_password", self.chap_password)
        self.owner = body.get("owner", self.owner)
        self.save()

    @classmethod
    def schema(cls, partial=False, many=False):
        return IscsiClientSchema(partial=partial, many=many)

    @classmethod
    def to_dict_many(cls, clients):
        return IscsiClientResponseSchema(many=True).dump(clients)

    def to_dict(self):
        """
        Serialize model method
        """
        return IscsiClientResponseSchema().dump(self)


class IscsiClientSchema(Schema):
    CLIENT_IQN_PATTERN = r"^iqn\.\d{4}-\d{2}\.[a-z0-9\-.]+(:[a-z0-9.@_\-]+)?$"
    CLIENT_NAME_PATTERN = r"^[a-z0-9._\-]+$"
    CHAP_USERNAME_PATTERN = r"^[A-Za-z0-9._@:\-]+$"
    CHAP_PASSWORD_PATTERN = r"^[A-Za-z0-9._@:/\-]+$"

    id = fields.Int(dump_only=True)
    name = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(min=1, max=24),
            validate.Regexp(regex=CLIENT_NAME_PATTERN)
        )
    )
    chap_username = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(min=8, max=64),
            validate.Regexp(CHAP_USERNAME_PATTERN)
        )
    )
    chap_password = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(min=12, max=16),
            validate.Regexp(CHAP_PASSWORD_PATTERN)
        )
    )
    iqn = fields.String(
        required=True,
        validate=validate.And(
            validate.Length(min=1, max=128),
            validate.Regexp(CLIENT_IQN_PATTERN)
        )
    )
    owner = fields.String(required=True, validate=validate.Email())
    account_id = fields.Int(required=True, load_only=True)


class IscsiClientResponseSchema(IscsiClientSchema):
    account = fields.Nested("AccountSchema", dump_only=True)
    disks = fields.Nested("IscsiDiskSchema", dump_only=True, many=True)


def before_delete(mapper, connection, client_instance):
    """
    Listener function, called before deleting an IscsiClients object.
    """
    from app.models.iscsi_target import IscsiTargets
    targets = IscsiTargets.get_account_targets(account_id=client_instance.account_id)

    for target in targets:
        try:
            iscsi_service = target.iscsi_service()
        except ValueError as e:
            log.warning(
                f"Skipping target '{target.iqn}' — {e}"
            )
            continue

        log.info(
            f"Attempting to delete client '{client_instance.name}' from target '{target.iqn}'"
        )

        response = iscsi_service.delete_client(client_iqn=client_instance.iqn)

        if is_failed(response):
            log.error(
                f"Failed to delete client '{client_instance.name}' from target '{target.iqn}': "
                f"{response['data']}"
            )
            abort(response["code"], response["data"])

        log.info(
            f"Client '{client_instance.name}' successfully deleted from target '{target.iqn}'"
        )


event.listen(IscsiClients, "before_delete", before_delete)
