"""
iSCSI Config model
"""
import re
from json import loads
from flask import abort
from sqlalchemy import event

from app.database import db
from app.lib.request_utils import is_failed
from app.loggers import log
from app.models.model import AbstractModel
from app.models.pool import Pools, PoolSchema

class IscsiConfigs(db.Model, AbstractModel):

    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "iscsi.configs"
    id = db.Column(db.Integer, primary_key=True)
    target_iqn = db.Column(db.String(256))
    pool_id = db.Column(db.Integer, db.ForeignKey("pools.id"))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    name = db.Column(db.String(128))
    gateways = db.relationship(
        "IscsiGateways", backref="gateways", cascade="all, delete-orphan"
    )
    disks = db.relationship(
        "IscsiDisks", backref="iscsi_disks", cascade="all, delete-orphan"
    )

    def __repr__(self):
        """
        Return a string representation of the IscsiConfigs object.
        """
        return f"IscsiConfigs({self.id}, {self.name}, {self.target_iqn}, \
            {self.account_id}, {self.account_id}, {self.gateways})"

    def save(self):
        """
        Save the current object to the database.

        :return: The result of committing the object to the database.
        """

        return self._commit(db)

    def remove(self):
        """
        Method to remove the object from the database.
        """

        self._delete(db)
        """
        Method to remove the object from the database.
        """

        self._delete(db)

    def serialize(self, hide_params=None):
        """
        Serialize the object's attributes and return the filtered response.

        :param hide_params: A list of parameters to hide from the serialized response.
        :type hide_params: list, optional

        :return: The filtered response containing the serialized attributes.
        :rtype: dict
        """

        super()._serialize()
        fields = {
            "id": "self.id",
            "target_iqn": "self.target_iqn",
            "pool": "self._pool()",
            "account": "self._account()",
            "gateways": "self._gateways()",
        }
        return self.response_filter(fields, hide_params)

    def _pool(self):
        """
        Retrieve and serialize the pool with the given ID.
        """
        return PoolSchema().dump(Pools.get_by("id", self.pool_id))

    def _account(self):
        """
        Retrieve the account information associated with the given account ID.

        :return: Serialized account information including quotas.
        :rtype: dict
        """
        from app.models.account import Accounts, AccountSchema  # fix circular import
        account = Accounts.get_by("id", self.account_id)
        return AccountSchema().dump(account)

    def _gateways(self):
        """
        Retrieves and serializes the IscsiGateways associated with the current instance.
        Returns a list of serialized IscsiGateway objects.
        """
        from app.models.iscsi_gateway import IscsiGateways, IscsiGatewaySchema  # fix circular import

        return [
            IscsiGatewaySchema().dump(i)
            for i in self.gateways
        ]

    def iscsi_service(self, ensure_exist: bool = True):
        from app.lib.iscsi_utils import Iscsi

        if not self.gateways:
            log.warning(f"No gateway for config {self.target_iqn}")
            raise ValueError("No gateway for this config.")
        iscsi_service = Iscsi(config=self, gateway=self.gateways[0])

        if ensure_exist and is_failed(iscsi_service.get_target()):
            log.warning(f"Target {self.target_iqn} was deleted.")
            raise ValueError(f"Target {self.target_iqn} was deleted.")

        return iscsi_service


from marshmallow import Schema, fields, validate


class IscsiConfigSchema(Schema):
    CONFIG_IQN_PATTERN = r"^iqn\.\d{4}-\d{2}\.[a-z0-9\-.]+(:[a-z0-9.@_\-]+)?$"
    CONFIG_NAME_PATTERN = r"^[a-z0-9._\-]+$"

    id = fields.Int(dump_only=True)
    pool_id = fields.Int(load_only=True)
    account_id = fields.Int(load_only=True)

    target_iqn = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=64),
            validate.Regexp(regex=CONFIG_IQN_PATTERN)
        )
    )
    name = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=64),
            validate.Regexp(regex=CONFIG_NAME_PATTERN)
        )
    )

    pool = fields.Function(lambda config: config._pool(), dump_only=True)
    account = fields.Function(lambda config: config._account(), dump_only=True)
    gateways = fields.Function(lambda config: config._gateways(), dump_only=True)


def before_delete(mapper, connection, config_instance):
    """
    Listener function, called before deleting an IscsiConfigs object.
    """
    from app.lib.iscsi_utils import Iscsi
    log.info(f"Deleting target in Cloud Gateway (name={config_instance.name}).")

    try:
        iscsi_service = config_instance.iscsi_service()
    except ValueError as e:
        return

    deleted_clients = []
    if not config_instance.gateways:
        log.warning(
                f"No gateways found for config (target_iqn={config_instance.target_iqn})."
            )
        return

    for disk in config_instance.disks:
        for client in disk.clients:
            if client.id in deleted_clients:
                continue

            log.info(
                f"Attempting to delete client '{client.name}' "
                f"for target (target_iqn={config_instance.target_iqn})."
            )

            response = iscsi_service.delete_client(client)

            if is_failed(response):
                abort(400, response["data"])

            deleted_clients.append(client.id)

    response = iscsi_service.delete_target()
    if is_failed(response):
        abort(response["code"], response["data"])

    log.info(
        f"Successfully deleted target in Cloud Gateway (name={config_instance.name})."
    )


event.listen(IscsiConfigs, "before_delete", before_delete)
