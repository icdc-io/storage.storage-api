"""
S3 Bucket Model
"""

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.lib.ceph_utils import ceph_connection as rgwadmin_conn
from app.lib.request_utils import log


class Bucket:
    def __init__(self, name, path, user_name, quota, bucket_info=None):
        self.path = path
        self.name = name
        self.user_name = user_name
        self.quota = quota or BucketQuota(0, 0)
        self._bucket_info_cache = bucket_info

    def __repr__(self):
        return f"<Buckets(name={self.name}, user={self.user_name}, quota={self.quota})>"

    @staticmethod
    def get_all_buckets_info() -> list[dict]:
        """
        Get info of all buckets.
        """
        log.info("Get info of all buckets in ceph")
        buckets_info = rgwadmin_conn().request(
            "GET", "/admin/bucket?format=json&stats=True"
        )
        return buckets_info

    @staticmethod
    def get_bucket_info(path):
        """
        Get info of one bucket.
        """
        bucket_info = rgwadmin_conn().request(
            "GET", f"/admin/bucket?format=json&stats=True&bucket={path}"
        )
        return bucket_info

    @property
    def bucket_info(self):
        """
        Getter for bucket info.
        """
        if self._bucket_info_cache is None:
            self._bucket_info_cache = self.get_bucket_info(self.path)
        return self._bucket_info_cache

    @classmethod
    def from_user_and_bucket_name(cls, user_name: str, bucket_name: str):
        """
        Constructor of class by user_name and bucket_name.
        """
        path = f"{user_name.split('$')[0]}/{bucket_name}" if '$' in user_name else bucket_name
        return cls.from_bucket_path(path)

    @classmethod
    def from_bucket_path(cls, path):
        """
        Constructor of class by path.
        """
        bucket_info = Bucket.get_bucket_info(path)
        return cls.from_bucket_info(bucket_info)

    @classmethod
    def from_bucket_info(cls, bucket_info: dict):
        """
        Constructor of class by prepared bucket_info.
        """
        quota = BucketQuota.from_ceph_quota_info(bucket_info["bucket_quota"])
        if not bucket_info["tenant"]:
            path = bucket_info["bucket"]
        else:
            path = bucket_info["tenant"] + '/' + bucket_info["bucket"]
        return cls(
            path=path,
            name=bucket_info["bucket"],
            user_name=bucket_info["owner"],
            quota=quota,
            bucket_info=bucket_info
        )

    def get_usage(self):
        """
        Get usage of bucket.
        """
        usage_info = self.bucket_info.get("usage", {})
        main_usage = usage_info.get("rgw.main", {})
        multimeta_usage = usage_info.get("rgw.multimeta", {})

        objects = main_usage.get("num_objects", 0)
        multipart_objects = multimeta_usage.get("num_objects", 0)
        total_objects = objects + multipart_objects

        usage = {
            "data_size_mb": main_usage.get("size_actual", 0) // 1024 ** 2,
            "total_objects": total_objects,
            "objects": objects,
            "multipart_objects": multipart_objects
        }

        return usage

    def filter(self, filters):
        """
        Check whether the bucket satisfies the filter conditions.
        """
        bucket_dict = self.to_dict()
        for key in filters:
            if key not in bucket_dict.keys():  # allow to filter by any field in serialization
                raise AttributeError(f"Invalid filter key '{key}'")
            # NOTE: Filter values are always a string or dict (for related objects)
            filter_value = filters[key]
            if isinstance(filter_value, dict):  # filter by related objects
                if isinstance(bucket_dict[key], dict):
                    related_object = bucket_dict[key]
                    for related_key in filter_value.keys():
                        if related_object.get(related_key) != filter_value[related_key]:
                            return False
                else:
                    raise AttributeError(f"Invalid data type for filter key '{key}'")
            else:  # filter by bucket fields
                if str(bucket_dict.get(key)) != filter_value:
                    return False
        return True

    def to_dict(self):
        return BucketSchema().dump(self)


class BucketQuota:
    def __init__(self, data_size_mb, objects):
        self.data_size_mb = data_size_mb
        self.objects = objects

    def __repr__(self):
        return f"<BucketQuota(size={self.data_size_mb}MB, objects={self.objects})>"

    @classmethod
    def from_ceph_quota_info(cls, quota):
        quota["max_size"] = -1 if quota["max_size"] < 0 else quota["max_size"] / 1024 / 1024
        return cls(
            data_size_mb=quota["max_size"],
            objects=quota["max_objects"],
        )

    def to_dict(self):
        return BucketQuotaSchema().dump(self)


class BucketQuotaSchema(Schema):
    data_size_mb = fields.Int(min=0)
    objects = fields.Int(min=0)


class BucketSchema(Schema):
    BUCKET_NAME_PATTERN = (
        r'^(?!xn--)'
        r'^(?!(\d{1,3}\.){3}\d{1,3}$)'
        r'(?!.*\.\.)'
        r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$'
    )

    path = fields.String()
    name = fields.String(
        validate=validate.And(
            validate.Length(min=3, max=63),
            validate.Regexp(regex=BUCKET_NAME_PATTERN)
        )
    )

    user_name = fields.String()
    quota = fields.Nested(BucketQuotaSchema())
    usage = fields.Function(lambda bucket: bucket.get_usage(), dump_only=True)

    @validates_schema
    def validate_bucket_schema(self, data, **kwargs):
        s3_user = self.context.get("user")
        bucket = self.context.get("bucket")

        errors = {}
        new_quota = data.get("quota", {})

        if data.get("name") and data.get("name") in s3_user.get_buckets_name():
            errors["Name"] = f"Bucket name must be unique. {data.get('name')} already in use."
        if data.get("name") and "/" in data.get("name"):
            errors["Name"] = "Bucket name should not contain slashes '/'"

        # Determine current quota
        if bucket:
            cur_quota = bucket.quota.to_dict()
        else:
            cur_quota = {"data_size_mb": -1, "objects": -1}

        for key in ["data_size_mb", "objects"]:
            new_quota[key] = new_quota.get(key, cur_quota.get(key))

        user_quota = s3_user.get_quota()
        for key in ["data_size_mb", "objects"]:
            if user_quota[key] < new_quota[key]:
                errors[key] = f"Bucket quota '{key}' must not exceed user quota."

        if errors:
            raise ValidationError(errors)
