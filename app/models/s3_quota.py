"""
S3 Quota model
"""
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)

from app import consts
from app.database import db
from app.models.model import AbstractModel
from app.models.pool import Pools


class S3Quotas(AbstractModel):
    RESOURCE_NAME = "s3.quotas"
    id = db.Column(db.Integer, primary_key=True)
    objects = db.Column(db.Integer)
    data_size_mb = db.Column(db.Integer)
    buckets = db.Column(db.Integer)
    users = db.Column(db.Integer)
    pool_id = db.Column(db.Integer, db.ForeignKey("pools.id"))
    pool = db.relationship("Pools", back_populates="s3_quotas")
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    account = db.relationship("Accounts", back_populates="s3_quotas")
    __table_args__ = (
        db.UniqueConstraint(
            "pool_id", "account_id", name="s3_quotas_pool_id_account_id"
        ),
    )

    def __repr__(self):
        return f"S3Quotas({self.id}, {self.objects}, {self.data_size_mb}, \
            {self.buckets}, {self.users}, {self.pool_id}, {self.account_id})"

    @classmethod
    def schema(cls):
        return S3QuotaSchema()

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.objects = body.get("objects", self.objects)
        self.data_size_mb = body.get("data_size_mb", self.data_size_mb)
        self.buckets = body.get("buckets", self.buckets)
        self.users = body.get("users", self.users)
        self.save()

    def get_restriction_names(self):
        return ["objects", "data_size_mb", "buckets", "users"]

    def compute_usage(self):
        from app.models.s3_user import S3Users

        usage = {
            'data_size_mb': 0,
            'objects': 0,
            'buckets': 0
        }

        users = S3Users.query.filter_by(pool_id=self.pool_id, account_id=self.account_id).all()
        for user in users:
            for key in usage.keys():
                usage[key] = usage.get(key, 0) + user.quota[key]

        usage = usage | {"users": len(users)}

        return usage

    # Query for default LimitSets for all pools
    # @DS: here we incapsulate logic with 'default' account
    @classmethod
    def get_default_limitsets(cls):
        from app.models.account import Accounts
        default_account = Accounts.query.filter_by(name=consts.ACCOUNT_DEFAULT).first()
        return cls.query.filter_by(account_id=default_account.id)
    
    # Get LimitSet for the pool
    @classmethod
    def get_pool_limitset(cls, pool_id):
        return cls.get_default_limitsets().filter_by(pool_id=pool_id).first()

    # Get LimitSet for the Quotas's pool
    def get_limitset(self):
        return self.get_pool_limitset(self.pool_id)

    # Used to prepare marshmallow restrictions for JSON output with QuotaSchema
    def get_schema_limits(self):
        limitset = self.get_limitset()
        return {restriction: getattr(limitset, restriction) for restriction in self.get_restriction_names()}

    def to_dict(self, *, is_limit: bool = False) -> dict:
        """
        Convert the S3Quotas object into a JSON-compatible dictionary.
        Args:
            is_limit (bool): If True, exclude non-limit fields.
        Returns:
            dict
        """
        exclude = {"limits", "usage", "endpoints"} if is_limit else set()
        return S3QuotaResponseSchema(exclude=exclude).dump(self)



class S3QuotaSchema(Schema):
    id           = fields.Int(dump_only=True)
    users        = fields.Int(validate=validate.Range(min=0), required=True)
    buckets      = fields.Int(validate=validate.Range(min=0), required=True)
    objects      = fields.Int(validate=validate.Range(min=0), required=True)
    data_size_mb = fields.Int(validate=validate.Range(min=0), required=True)
    account_id   = fields.Int(load_only=True, required=True)
    pool_id      = fields.Int(load_only=True, required=True)

    endpoints    = fields.Method("generate_endpoints", dump_only=True)
    usage        = fields.Function(lambda quota: quota.compute_usage(), dump_only=True)
    limits       = fields.Function(lambda quota: quota.get_schema_limits(), dump_only=True)
    pool         = fields.Nested("PoolSchema", dump_only=True)

    def generate_endpoints(self, obj):
        location_domain = consts.LOCATION_DOMAIN
        return {
                 "public": f"https://s3.{location_domain}",
                 "private": f"http://s3.local.{location_domain}"
               }

    @pre_load
    def set_limits(self, data, many, **kwargs):
        if not data.get("pool_id"):
            return data
        pool = self.__get_pool(data.get("pool_id", None))
        self.limits = S3Quotas.get_pool_limitset(pool.id)
        return data

    @validates_schema
    def validates_limit_exceeding(self, data, **kwargs):
        if not data.get("pool_id"):
            return data
        errors = {}
        usage = self.context.get("usage")

        for value in ["users", "objects", "buckets", "data_size_mb"]:
            if value in data:
                if data[value] > getattr(self.limits, value):
                    errors[value] = [f"Must be less than or equal to {getattr(self.limits, value)}."]
                elif usage and data[value] < usage[value]:
                    errors[value] = [f"The {value} must be greater than current in usage. {usage[value]}/{data[value]}"]
        if errors:
            raise ValidationError(errors)

    def __get_pool(self, id):
        pool = Pools.query.filter_by(id=id).first()
        if not pool:
            raise ValidationError("Must exist.", "pool")

        return pool


class S3QuotaResponseSchema(S3QuotaSchema):
    account      = fields.Nested("AccountSchema", dump_only=True)
