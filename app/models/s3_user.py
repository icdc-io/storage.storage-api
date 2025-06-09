"""
S3 User Model
"""
from enum import StrEnum

import rgwadmin.exceptions
from flask import abort
from sqlalchemy import event

from app.database import db
from app.lib.ceph_utils import ceph_connection as rgwadmin_conn
from app.loggers import log
from app.models.account import Accounts, AccountSchema
from app.models.model import AbstractModel
from app.models.pool import Pools, PoolSchema


class S3Users(db.Model, AbstractModel):
    """
    Define columns in database and methods of model
    """
    RESOURCE_NAME = "s3.users"
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(128))
    owner = db.Column(db.String(128))
    name = db.Column(db.String(128))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    pool_id = db.Column(db.Integer, db.ForeignKey("pools.id"))
    account = db.relationship("Accounts", back_populates="s3_users")
    pool = db.relationship("Pools", back_populates="s3_users")
    _user_info_cache = None

    def __repr__(self):
        return f"S3Users({self.id}, {self.description}, {self.owner}, \
            {self.name}, {self.account_id}, {self.pool_id})"

    @property
    def user_info(self):
        if self._user_info_cache is None:
            try:
                self._user_info_cache = rgwadmin_conn().get_user(self.name)
            except rgwadmin.exceptions.NoSuchUser as e:
                return {}
        return self._user_info_cache

    @property
    def status(self):
        if not self.user_info:
            return S3UserStatus.DELETED
        if self.user_info.get("suspended"):
            return S3UserStatus.LOCKED

        return S3UserStatus.ACTIVE

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
            "description": "self.description",
            "owner": "self.owner",
            "name": "self.name",
            "account": "self._account()",
            "pool": "self._get_pool()",
        }
        return self.response_filter(fields, hide_params)

    def _get_pool(self):
        return Pools.get_by("id", self.pool_id).serialize()

    def _account(self):
        return Accounts.get_by("id", self.account_id)

    def update(self, body):
        """
        UPDATE SET SQL
        """
        self.description = body.get("description", self.description)
        self.owner = body.get("owner", self.owner)
        if 'is_locked' in body:
            self._lock(body['is_locked'])
        self._user_info_cache = None
        self.save()

    def full_name(self):
        return self.name

    def _lock(self, action):
        """
        Suspend or unsuspend the S3 user
        """
        cases = {"lock": True, "unlock": False}
        if cases.get(action) != self.user_info['suspended']:
            rgwadmin_conn().modify_user(uid=self.name, suspended=cases.get(action))

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

    def get_quota(self):
        """
        Get the S3 user's quota.
        """
        if self.is_deleted():
            return S3UserQuota.default().to_dict()
        quota = S3UserQuota.from_user_info(self.user_info)
        return quota.to_dict()

    def get_keys(self):
        """
        Get the S3 user's access keys and Swift keys.
        """
        s3_keys_list = self.user_info.get("keys", [])
        swift_keys_list = self.user_info.get("swift_keys", [])

        return {
            "s3": s3_keys_list[0] if s3_keys_list else {},
            "swift": swift_keys_list[0] if swift_keys_list else {}
        }

    def get_usage(self):
        """
        Get the usage statistics for the S3 user.
        """
        if self.is_deleted():
            return S3UserQuota.default().to_dict()

        if self.is_locked():
            return S3UserQuota.from_user_info(self.user_info).to_dict()

        keys = self.get_keys()
        access_key = keys["s3"]["access_key"]
        secret_key = keys["s3"]["secret_key"]
        usage_info = rgwadmin_conn(access_key=access_key, secret_key=secret_key).request(
            "GET", "/?usage&format=json"
        )
        return S3UserQuota.from_usage_info(usage_info).to_dict()

    def get_buckets_name(self):
        """
        Get Bucket of S3 User.
        """

        buckets_name = rgwadmin_conn().request(
            "GET", f"/admin/bucket?format=json&uid={self.name}"
        )

        return buckets_name


class S3UserStatus(StrEnum):
    DELETED = "deleted"
    LOCKED = "locked"
    ACTIVE = "active"


class S3UserQuota:
    def __init__(self, data_size_mb=0, objects=0, buckets=0):
        self.data_size_mb = data_size_mb
        self.objects = objects
        self.buckets = buckets

    def __repr__(self):
        return f"<S3UserQuota(data_size_mb={self.data_size_mb}, objects={self.objects}, buckets={self.buckets})>"

    @classmethod
    def from_user_info(cls, user_info):
        return cls(
            data_size_mb=user_info["user_quota"]["max_size_kb"] // 1024,
            objects=user_info["user_quota"]["max_objects"],
            buckets=user_info["max_buckets"]
        )

    @classmethod
    def from_usage_info(cls, usage_info):
        return cls(
            data_size_mb=usage_info['Summary'][6] // (1024 * 1024),
            objects=usage_info['Summary'][7],
            buckets=len(usage_info['CapacityUsed'][0]['Buckets'])
        )

    @classmethod
    def default(cls):
        return cls(
            data_size_mb=0,
            objects=0,
            buckets=0
        )

    def to_dict(self):
        return S3UserQuotaSchema().dump(self)


from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    validate,
    validates_schema,
)


class S3UserQuotaSchema(Schema):
    data_size_mb = fields.Int(validate=validate.Range(min=0))
    objects = fields.Int(validate=validate.Range(min=0))
    buckets = fields.Int(validate=validate.Range(min=0))

class S3UserSchema(Schema):
    id = fields.Int(dump_only=True)
    description = fields.String()
    owner = fields.String()
    name = fields.String()
    account_id = fields.Int(load_only=True)
    pool_id = fields.Int(load_only=True)
    account = fields.Nested(AccountSchema(), dump_only=True)
    pool = fields.Nested(PoolSchema(), dump_only=True)
    quota = fields.Nested(S3UserQuotaSchema(), load_only=True)
    user_quota = fields.Function(lambda s3user: s3user.get_quota(), dump_only=True)
    keys = fields.Function(lambda s3user: s3user.get_keys(), dump_only=True)
    usage = fields.Function(lambda s3user: s3user.get_usage(), dump_only=True)
    status = fields.Function(lambda s3user: s3user.status, dump_only=True)

    class Meta:
        unknown = EXCLUDE

    @validates_schema
    def validate_user_quota(self, data, **kwargs):
        new_quota = data.get("quota")
        if not new_quota:
            return
        errors: dict = {}

        account_quota = self.context.get("account_quota")
        if not account_quota:
            return

        errors.update(S3UserQuotaSchema().validate(new_quota))

        cur_quota = {"data_size_mb": 0, "objects": 0, "buckets": 0}
        usage = None
        if self.context.get("user"):
            s3_user = self.context.get("user")
            cur_quota = s3_user.get_quota()
            usage = s3_user.get_usage()

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

        if errors:
            raise ValidationError(errors)


def before_delete(mapper, connection, s3_user_instance):
    """
    Listener function, called before deleting a S3_user object.
    """
    try:
        log.info(f"Deleting s3 user in Ceph "
                 f"(name = {s3_user_instance.name})")
        rgwadmin_conn().remove_user(s3_user_instance.name, purge_data=True)
        log.info(f"Delete s3 user in Ceph "
                 f"(name = {s3_user_instance.name}) was successful")
    except rgwadmin.exceptions.NoSuchUser as e:
        log.warning(f"No such user: {s3_user_instance.name}")
    except rgwadmin.exceptions.AccessDenied as e:
        abort(403, str(e))
    except rgwadmin.exceptions.RGWAdminException as e:
        abort(400, str(e))


event.listen(S3Users, "before_delete", before_delete)
