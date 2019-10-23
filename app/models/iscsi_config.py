"""
iSCSI Config model
"""
from app.database import db
from app.models.model import AbstractModel
from app.models.pool import Pools, PoolSchema


class IscsiConfigs(db.Model, AbstractModel):

    """
    Define columns in database and methods of model
    """

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
        return PoolSchema(exclude=["s3_placement_target"]).dump(Pools.get_by("id", self.pool_id))

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


from marshmallow import Schema, fields
from app import consts


class IscsiConfigSchema(Schema):
    id = fields.Int(dump_only=True)
    target_iqn = fields.String(dump_only=True)
    pool_id = fields.Int(dump_only=True)
    account_id = fields.Int(dump_only=True)
    name = fields.String()
    pool = fields.Function(lambda config: config._pool(), dump_only=True)
    account = fields.Function(lambda config: config._account(), dump_only=True)
    gateways = fields.Function(lambda config: config._gateways(), dump_only=True)
