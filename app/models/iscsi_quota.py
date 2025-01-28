"""
iSCSI Quota Model
"""

from app.database import db
from app.models.model import AbstractModel
from app.models.pool import Pools, PoolSchema


class IscsiQuotas(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """

    id = db.Column(db.Integer, primary_key=True)
    clients = db.Column(db.Integer)
    data_size_gb = db.Column(db.Integer)
    disks = db.Column(db.Integer)
    snapshots = db.Column(db.Integer)
    pool_id = db.Column(db.Integer, db.ForeignKey("pools.id"))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    pool = db.relationship("Pools", back_populates="iscsi_quotas")
    __table_args__ = (
        db.UniqueConstraint(
            "pool_id", "account_id", name="iscsi_quotas_pool_id_account_id"
        ),
    )

    def save(self):
        """
        INSERT SQL
        """
        self._commit(db)

    def __repr__(self):
        return f"ISCSIQuotas({self.id}, {self.clients},{self.data_size_gb}, \
            {self.disks}, {self.pool_id}, {self.pool_id}, {self.account_id})"

    def serialize(self, hide_params=None):
        """
        Serialize model method
        """
        super()._serialize()
        fields = {
            "id": "self.id",
            "clients": "self.clients",
            "data_size_gb": "self.data_size_gb",
            "disks": "self.disks",
            "pool": "self._pool()",
            "snapshots": "self.snapshots",
        }
        return self.response_filter(fields, hide_params)

    def _pool(self):
        return Pools.get_by("id", self.pool_id).serialize()

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.clients = body.get("clients", self.clients)
        self.disks = body.get("disks", self.disks)
        self.data_size_gb = body.get("data_size_gb", self.data_size_gb)
        self.snapshots = body.get("snapshots", self.snapshots)
        self.save()

    def get_restriction_names(self):
        return ["clients", "data_size_gb", "disks", "snapshots"]

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.clients = body.get("clients", self.clients)
        self.data_size_gb = body.get("data_size_gb", self.data_size_gb)
        self.disks = body.get("disks", self.disks)
        self.snapshots = body.get("snapshots", self.snapshots)
        self.save()

    def _config(self):
        """
        Retrieves and serializes the IscsiConfigs object by "id" and returns a subset of its data containing the "gateways" field.
        """
        from app.models.iscsi_config import IscsiConfigs  # fix circular import

        return IscsiConfigs.get_by("account_id", self.account_id).serialize(["account"])

    def _config_all(self):
        """
        Retrieves all IscsiConfigs objects filtered by "account_id" and returns their data, focusing on the "gateways" field.
        """
        from app.models.iscsi_config import IscsiConfigs, IscsiConfigSchema # fix circular import

        # Assuming 'serialize' is a method that formats the query results and 'gateways' is included in the serialization
        iscsi_configs = IscsiConfigs.query.filter_by(account_id = self.account_id, pool_id = self.pool_id).all()
        return [IscsiConfigSchema(exclude=['pool','gateways','account','account_id','account']).dump(config) for config in iscsi_configs]

    def compute_usage(self):
        from app.models.iscsi_disk import IscsiDisks

        usage = dict.fromkeys(self.get_restriction_names(), 0)
        usage |= {"snapshots_size_gb":0}
        clients = set()
        disks = []
        for config in self._config_all():
            disks += IscsiDisks.query.filter_by(config_id=config.get("id")).all()

        for disk in disks:
            disk_usage = disk.get_usage()
            for key in disk_usage.keys():
                usage[key] += disk_usage[key]
                for snapshot in disk.snapshots:
                    usage["snapshots_size_gb"] += snapshot.size_gb
                for client in disk.clients:
                    clients.add(client.id)
        usage['clients'] = len(clients)

        return usage

    def get_limits(self):
        from app.models.account import Accounts

        default_account = Accounts.query.filter_by(name=consts.ACCOUNT_DEFAULT).first()
        limits = self.query.filter_by(account_id=default_account.id, pool_id=self.pool_id).first()
        return {restriction: getattr(limits, restriction) for restriction in self.get_restriction_names()}

    def toDict(self, exclude_fields=set()) -> dict:
        """
        Convert model instance to JSON-serializable dictionary, optionally excluding specified fields.

        Args:
            exclude_fields (set): Field names to exclude from the serialized output.

        Returns:
            dict: JSON-serializable dictionary representation of the model instance.
        """
        data = {
            "id": self.id,
            "clients": self.clients,
            "data_size_gb": self.data_size_gb,
            "disks": self.disks,
            "snapshots": self.snapshots,
            "pool_id": self.pool_id,
            "account_id": self.account_id,
            "configs": self._config_all(),
        }

        for field in exclude_fields:
            data.pop(field, None)

        return data


from marshmallow import Schema, fields, validate, pre_load, ValidationError, validates_schema, pre_dump
from app import consts


class IscsiQuotaSchema(Schema):
    id = fields.Int(dump_only=True)
    clients = fields.Int(validate=validate.Range(min=0))
    data_size_gb = fields.Int(validate=validate.Range(min=0))
    disks = fields.Int(validate=validate.Range(min=0))
    snapshots = fields.Int(validate=validate.Range(min=0))
    pool_id = fields.Int(load_only=True)
    pool = fields.Nested(PoolSchema(), dump_only=True)
    account_id = fields.Int()
    limits = fields.Function(lambda quota: quota.get_limits(), dump_only=True)
    configs = fields.Function(lambda quota: quota._config_all(), dump_only=True)
    usage = fields.Function(lambda quota: quota.compute_usage(), dump_only=True)

    @pre_load
    def set_limits(self, data, many, **kwargs):
        default_account = self.__get_default_account()
        if not data.get("pool_id"):
            return data
        pool = self.__get_pool(data.get("pool_id", None))
        self.limits = IscsiQuotas.query.filter_by(account_id=default_account.id, pool_id=pool.id).first()

        return data

    @validates_schema
    def validates_limits_exceeding(self, data, **kwargs):
        errors = {}
        usage = self.context.get("usage")
        for value in ["clients", "data_size_gb", "disks", "snapshots"]:
            if value in data:
                if data[value] > getattr(self.limits, value):
                    errors[value] = [f"Must be less than or equal to {getattr(self.limits, value)}."]
                elif usage and data[value] < usage[value]:
                    errors[value] = [f"The {value} must be greater that current in usage. "
                                     f"{usage[value]}/{data[value]}"]

        if errors:
            raise ValidationError(errors)

    def __get_default_account(self):
        import os
        from app.models.account import Accounts
        return Accounts.query.filter_by(name=consts.ACCOUNT_DEFAULT).first()

    def __get_pool(self, id):
        pool = Pools.query.filter_by(id=id).first()
        if not pool:
            raise ValidationError("Must exist.", "pool")
        return pool
