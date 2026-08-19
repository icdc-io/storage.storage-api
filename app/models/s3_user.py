"""
S3 User Model
"""
from enum import StrEnum

import rgwadmin.exceptions
from flask import abort
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)
from sqlalchemy import event

from app.database import db
from app.lib.s3.operations import S3UserQuery
from app.loggers import log
from app.models.account import AccountSchema
from app.models.model import AbstractModel
from app.models.pool import PoolSchema


class S3UserStatus(StrEnum):
    UNKNOWN = "unknown"
    DELETED = "deleted"
    LOCKED = "locked"
    ACTIVE = "active"


DEFAULT_QUOTA = {
    "data_size_mb": 0,
    "objects": 0,
    "buckets": 0
}


class S3Users(AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "s3.users"
    query_class = S3UserQuery

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(128))
    owner = db.Column(db.String(128))
    name = db.Column(db.String(128))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    pool_id = db.Column(db.Integer, db.ForeignKey("pools.id"))
    account = db.relationship("Accounts", back_populates="s3_users")
    pool = db.relationship("Pools", back_populates="s3_users")

    status = S3UserStatus.UNKNOWN
    usage = {}
    quota = {}
    keys = {}

    @classmethod
    def _get_related_filters(cls) -> dict:
        from app.models.pool import Pools

        return {
            'pool': ("pool", Pools),
        }

    def __repr__(self):
        return f"S3Users({self.id}, {self.description}, {self.owner}, \
            {self.name}, {self.account_id}, {self.pool_id})"

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.description = body.get("description", self.description)
        self.owner = body.get("owner", self.owner)
        self.save()

    def inject_ceph_state(self, data: dict = None):
        if not data:
            data = {}

        self.status = data.get("status", S3UserStatus.DELETED)

        self.usage = data.get("usage") or DEFAULT_QUOTA.copy()
        self.quota = data.get("quota") or DEFAULT_QUOTA.copy()

        self.keys = data.get("keys") or {"s3": {}, "swift": {}}

    def is_deleted(self):
        """
        Check deletion of s3 user.
        """
        return self.status == S3UserStatus.DELETED

    def is_locked(self):
        """
        Check is user locked.
        """
        return self.status == S3UserStatus.LOCKED

    @classmethod
    def schema(cls):
        return S3UserSchema()


class S3UserQuotaSchema(Schema):
    data_size_mb = fields.Int(validate=validate.Range(min=0))
    objects = fields.Int(validate=validate.Range(min=0))
    buckets = fields.Int(validate=validate.Range(min=0))


class S3UserSchema(Schema):
    USER_NAME_PATTERN = r"^(?:[^$]*\$)?([a-z0-9._@\-]+)$"
    USER_DESCRIPTION_PATTERN = r"^[\w ,.:/;\[\]!@^*()_\-+=]*$"

    id = fields.Int(dump_only=True)
    description = fields.String(
        validate=validate.And(
            validate.Length(min=0, max=64),
            validate.Regexp(regex=USER_DESCRIPTION_PATTERN)
        )
    )
    name = fields.String(
        validate=validate.And(
            # Max length = 89: 24 for account prefix + 1 for '$' delimiter + remaining part
            validate.Length(min=1, max=89),
            validate.Regexp(regex=USER_NAME_PATTERN)
        ),
        required=True
    )
    owner = fields.String(validate=validate.Email(), required=True)
    account_id = fields.Int(load_only=True, required=True)
    pool_id = fields.Int(load_only=True, required=True)

    account = fields.Nested(AccountSchema(), dump_only=True)
    pool = fields.Nested(PoolSchema(), dump_only=True)

    status = fields.String(
        serialize=lambda s3user: s3user.status,
        deserialize=lambda value: value,
        validate=validate.OneOf([status.value for status in S3UserStatus]),
    )
    quota = fields.Dict(serialize=lambda s3user: s3user.quota, deserialize=lambda value: value, required=True)
    usage = fields.Dict(dump_only=True)
    keys = fields.Dict(dump_only=True)

    @validates_schema
    def validate_user_quota(self, data, **kwargs):
        new_quota = data.get("quota")
        if not new_quota:
            return
        errors: dict = {}

        account_quota = self.context.get("account_quota")
        if not account_quota:
            return

        try:
            new_quota = S3UserQuotaSchema().load(new_quota)
        except ValidationError as e:
            raise e

        cur_quota = {"data_size_mb": 0, "objects": 0, "buckets": 0}
        usage = None
        if self.context.get("user"):
            s3_user = self.context.get("user")
            cur_quota = s3_user.quota
            usage = s3_user.usage

        new_quota = {
            key: new_quota.get(key, cur_quota[key])
            for key in ["data_size_mb", "objects", "buckets"]
        }

        for key in ["data_size_mb", "objects", "buckets"]:
            if new_quota.get(key) and new_quota[key] > getattr(account_quota, key):
                errors[key] = f"S3User quota '{key}' must not exceed account quota."
            elif usage and new_quota[key] < usage[key]:
                errors[key] = f"Requested S3 user quota {new_quota[key]} can not be less than current usage: {usage[key]}"

        # Difference between current user quota and requested user quota
        delta = {
            key: new_quota[key] - cur_quota[key]
            for key in ["data_size_mb", "objects", "buckets"]
        }
        account_usage = account_quota.compute_usage()

        for key in ["data_size_mb", "objects", "buckets"]:
            if account_usage[key] + delta[key] > getattr(account_quota, key):
                errors[key] = (
                    f"Overflow of account quota on {key}: {account_usage[key] + delta[key]}"
                    f"/{getattr(account_quota, key)}"
                )

        if not usage and account_usage["users"] + 1 > getattr(account_quota, "users"):
            errors["users"] = "Overflow of account quota on users"

        if errors:
            raise ValidationError(errors)


def before_delete(mapper, connection, s3_user_instance):
    """
    Listener function, called before deleting a S3_user object.
    """
    try:
        from app.lib.s3.service import CephService
        log.info(f"Deleting s3 user in Ceph "
                 f"(name = {s3_user_instance.name})")
        CephService().remove_s3_user(s3_user_instance)
        log.info(f"Delete s3 user in Ceph "
                 f"(name = {s3_user_instance.name}) was successful")
    except rgwadmin.exceptions.NoSuchUser:
        log.warning(f"No such user: {s3_user_instance.name}")
    except rgwadmin.exceptions.AccessDenied as e:
        abort(403, str(e))
    except rgwadmin.exceptions.RGWAdminException as e:
        abort(400, str(e))


event.listen(S3Users, "before_delete", before_delete)
