"""
Pool model
"""
from marshmallow import Schema, fields, validate

from app.database import db
from app.models.model import AbstractModel


class Pools(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(128))
    name = db.Column(db.String(128))
    klass = db.Column(db.String(128))
    config = db.relationship(
        "IscsiConfigs", backref="pool-config", cascade="all, delete-orphan"
    )
    s3_quotas = db.relationship("S3Quotas", back_populates="pool", cascade="all, delete-orphan")
    s3_users = db.relationship("S3Users", back_populates="pool", cascade="all, delete-orphan")
    iscsi_quotas = db.relationship("IscsiQuotas", back_populates="pool", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Pool('{self.id}', '{self.name}', '{self.type}', {self.klass})"

    def save(self):
        """
        INSERT SQL
        """
        self._commit(db)

    def location_constraint(self):
        return f"default:{self.klass}"

    def serialize(self, hide_params=None):
        """
        Serialize model method
        """
        super()._serialize()
        fields = {
            "id": "self.id",
            "name": "self.name",
            "type": "self.type",
            "class": "self.klass",
        }
        return self.response_filter(fields, hide_params)


class PoolSchema(Schema):
    POOL_NAME_PATTERN = r"^[a-z0-9\-]$"
    POOL_KLASS_PATTERN = r"^[a-z\-]$"
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
