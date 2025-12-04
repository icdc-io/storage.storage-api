"""
Pool model
"""
from marshmallow import Schema, fields, validate

from app import consts
from app.database import db
from app.models.model import AbstractModel


class Pools(AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "pools"
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(128))
    name = db.Column(db.String(128))
    klass = db.Column(db.String(128))
    s3_quotas = db.relationship("S3Quotas", back_populates="pool", cascade="all, delete-orphan")
    s3_users = db.relationship("S3Users", back_populates="pool", cascade="all, delete-orphan")
    iscsi_quotas = db.relationship("IscsiQuotas", back_populates="pool", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Pool('{self.id}', '{self.name}', '{self.type}', {self.klass})"

    @classmethod
    def schema(cls, partial=False, many=False):
        return PoolSchema(partial=partial, many=many)

    def location_constraint(self):
        return f"default:{self.klass}"

    def get_target_iqn(self):
        return f"iqn.2020-01.{'.'.join(consts.LOCATION_DOMAIN.split('.')[::-1])}:iscsi-{self.name}"

    def to_dict(self):
        return PoolSchema().dump(self)


class PoolSchema(Schema):
    POOL_NAME_PATTERN = r"^[a-z0-9\-]+$"
    POOL_KLASS_PATTERN = r"^[a-z\-]+$"
    POOL_TYPE_CHOICES = ("iscsi", "s3")

    id = fields.Int()
    name = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=128),
            validate.Regexp(POOL_NAME_PATTERN)
        )
    )
    klass = fields.String(
        validate=validate.And(
            validate.Length(min=1, max=128),
            validate.Regexp(POOL_KLASS_PATTERN)
        )
    )
    type = fields.String(
        validate=validate.OneOf(POOL_TYPE_CHOICES)
    )
