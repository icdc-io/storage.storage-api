"""
S3 Bucket Model
"""

from marshmallow import Schema, fields, ValidationError, validates_schema
from app.lib.ceph_utils import ceph_connection as rgwadmin_conn


class Bucket:
    def __init__(self, name, path, user_name, quota):
        self.path = path
        self.name = name
        self.user_name = user_name
        self.quota = quota or BucketQuota(0, 0)

    def __repr__(self):
        return f"<Buckets(name={self.name}, user={self.user_name}, quota={self.quota})>"

    @classmethod
    def from_bucket_path(cls, path):
        bucket_info = rgwadmin_conn().request(
            "GET", f"/admin/bucket?format=json&stats=True&bucket={path}"
        )
        quota = BucketQuota.from_ceph_quota_info(bucket_info["bucket_quota"])

        return cls(
            path=path,
            name=bucket_info["bucket"],
            user_name=bucket_info["owner"],
            quota=quota,
        )

    @classmethod
    def from_user_and_bucket_name(cls, user_name, bucket_name):
        bucket_info_list = rgwadmin_conn().request(
            "GET",
            f"/admin/bucket?format=json&stats=True&bucket={bucket_name}&uid={user_name}",
        )
        bucket_info = bucket_info_list[0]
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
        )

    def get_usage(self):
        bucket_info = rgwadmin_conn().request(
            "GET",
            f"/admin/bucket?format=json&stats=True&bucket={self.path}",
        )

        usage_info = bucket_info.get("usage", {})
        main_usage = usage_info.get("rgw.main", {})
        multimeta_usage = usage_info.get("rgw.multimeta", {})

        objects = main_usage.get("num_objects", 0)
        multipart_objects = multimeta_usage.get("num_objects", 0)
        total_objects = objects + multipart_objects

        usage = {
            "data_size_mb": main_usage.get("size_actual", 0) // 1024**2,
            "total_objects": total_objects,
            "objects": objects,
            "multipart_objects": multipart_objects
        }

        return usage

    def filter(self, filters):
        bucket_dict = self.to_dict()
        for key in filters:
            if key not in bucket_dict.keys(): # allow to filter by any field in serialization
                raise AttributeError(f"Invalid filter key '{key}'")
            # NOTE: Filter values are always a string or dict (for related objects)
            filter_value = filters[key]
            if isinstance(filter_value, dict): # filter by related objects
                if isinstance(bucket_dict[key], dict):
                    related_object = bucket_dict[key]
                    for related_key in filter_value:
                        if str(related_object.get(related_key)) != filter_value[related_key]:
                            return False
                else:
                    raise AttributeError(f"Invalid data type for filter key '{key}'")
            else: # filter by bucket fields
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
    path = fields.String()
    name = fields.String()
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
