"""
Ceph Infrastructure Clients.
Provides Admin-level orchestration via RGWAdmin and User-level operations via Boto3.
"""

import boto3
import requests.exceptions as req_exceptions
import rgwadmin.exceptions as rgw_exceptions
from botocore.client import Config
from botocore.exceptions import ClientError
from rgwadmin import RGWAdmin
from typing import List, Any, Optional

from app import consts
from app.lib.s3 import paramiko
from app.lib.s3.exceptions import CephServiceException


class CephAdminClient:
    """
    Administrative client for Ceph RadosGW.
    Handles user management, quotas, and global bucket metadata.
    """

    def __init__(self) -> None:
        self.rgw = RGWAdmin(
            access_key=consts.CEPH_ACCESS_KEY,
            secret_key=consts.CEPH_SECRET_KEY,
            server=f"{consts.CEPH_HOST}:{consts.CEPH_PORT}",
            secure=False,
            verify=False,
        )

    def get_user_info(self, uid: str) -> dict:
        """Fetch raw user metadata from RGW."""
        try:
            return self.rgw.get_user(uid)
        except rgw_exceptions.NoSuchUser:
            return {}
        except rgw_exceptions.AccessDenied:
            raise CephServiceException(f"Forbidden: Admin keys cannot access user {uid}", code=403)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to fetch user {uid}", code=500, details=str(e))

    def update_user_placement_tags(self, uid: str, tags: str) -> Any:
        """Update RGW user tags using radosgw-admin command."""
        command = f"radosgw-admin user modify --uid '{uid}' --tags '{tags}'"
        return paramiko.send(command)

    def create_rgw_user(self, name: str, display_name: str, placement: str, max_buckets: int) -> dict:
        """Initialize a new RGW user account."""
        try:
            path = (
                f"/admin/user?format=json&uid={name}"
                f"&default-placement={placement}"
                f"&user-caps=buckets=*"
                f"&max-buckets={max_buckets}"
                f"&display-name={display_name}"
            )
            return self.rgw.request("PUT", path)
        except rgw_exceptions.UserExists:
            raise CephServiceException(f"User {name} already exists", code=400)
        except rgw_exceptions.RGWAdminException as e:
            raise CephServiceException(f"Ceph API error during user creation", code=502, details=str(e))
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to fetch user {name}", code=500, details=str(e))

    def set_user_quota(self, name: str, data_size_mb: int, objects: int) -> None:
        """Apply storage and object limits to a user."""
        try:
            self.rgw.set_user_quota(
                name, "user",
                max_size_kb=data_size_mb * 1024,
                max_objects=objects,
                enabled=True,
            )
        except rgw_exceptions.NoSuchUser:
            raise CephServiceException(f"Cannot set quota: User {name} not found", code=404)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to set quota for {name}", code=500, details=str(e))

    def create_swift_subuser(self, name: str) -> dict:
        """Provision a Swift subuser for the account."""
        try:
            return self.rgw.create_subuser(
                uid=name,
                subuser="swift",
                key_type="Swift",
                access="full",
                generate_secret=True
            )
        except rgw_exceptions.SubuserExists:
            raise CephServiceException(f"Swift subuser for {name} already exists", code=400)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to create Swift subuser for {name}", code=500, details=str(e))

    def remove_user(self, name: str) -> dict:
        """Purge user account and all associated data."""
        try:
            self.rgw.remove_user(name, purge_data=True)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except rgw_exceptions.NoSuchUser:
            return {}
        except Exception as e:
            raise CephServiceException(f"Failed to create Swift subuser for {name}", code=500, details=str(e))

    def modify_user(self, uid: str, **kwargs: Any) -> dict:
        """Update RGW user metadata attributes."""
        params = {k: v for k, v in kwargs.items() if v is not None}
        if not params:
            return {}

        try:
            return self.rgw.modify_user(uid=uid, **params)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except rgw_exceptions.NoSuchUser:
            raise CephServiceException(f"User {uid} not found", code=404)
        except Exception as e:
            raise CephServiceException(f"Failed to modify user {uid}", code=502, details=str(e))

    def set_bucket_quota(self, uid: str, bucket_name: str, data_size_mb: int, objects: int) -> dict:
        """Apply storage limits to a specific bucket."""
        try:
            return self.rgw.set_bucket_quota(
                uid=uid,
                bucket=bucket_name,
                max_size_kb=data_size_mb * 1024 if data_size_mb >= 0 else -1,
                max_objects=objects if objects >= 0 else -1,
                enabled=True
            )
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except rgw_exceptions.NoSuchUser:
            raise CephServiceException(f"User {uid} not found", code=404)
        except Exception as e:
            raise CephServiceException(f"Failed to set quota for bucket {bucket_name}", code=502, details=str(e))

    def get_bucket_info(self, bucket_path: str) -> dict:
        """Retrieve detailed stats for a specific bucket path."""
        try:
            return self.rgw.request(
                "GET", f"/admin/bucket?format=json&stats=True&bucket={bucket_path}"
            )
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except rgw_exceptions.NoSuchBucket:
            raise CephServiceException(f"Bucket {bucket_path} not found", code=404)
        except Exception as e:
            raise CephServiceException(f"Failed to fetch bucket info", code=502, details=str(e))

    def get_buckets_by_user(self, uid: str, stats: bool = True) -> List[dict]:
        """List all buckets owned by a specific user."""
        try:
            return self.rgw.request("GET", f"/admin/bucket?format=json&stats={stats}&uid={uid}")
        except rgw_exceptions.NoSuchUser:
            raise CephServiceException(f"User {uid} not found", code=404)
        except Exception:
            raise CephServiceException(f"Failed to fetch buckets for {uid}", code=502)

    def get_all_buckets_info(self) -> List[dict]:
        """Fetch stats for all buckets in the cluster."""
        try:
            return self.rgw.request("GET", "/admin/bucket?format=json&stats=True")
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to fetch bucket info", code=502, details=str(e))

    def remove_bucket(self, bucket_path: str, purge: bool = False) -> dict:
        """Remove a bucket and optionally purge its objects."""
        try:
            return self.rgw.remove_bucket(bucket=bucket_path, purge_objects=purge)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except rgw_exceptions.NoSuchBucket:
            raise CephServiceException(f"Bucket {bucket_path} not found", code=404)
        except Exception as e:
            raise CephServiceException(f"Failed to remove bucket", code=502, details=str(e))

    def remove_key(self, uid: str, access_key: str) -> dict:
        """Revoke a specific S3 access key from a user."""
        try:
            return self.rgw.request(
                "DELETE",
                f"/admin/user?format=json&key&uid={uid}&access-key={access_key}"
            )
        except rgw_exceptions.NoSuchUser:
            raise CephServiceException(f"User {uid} not found", code=404)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to delete key {access_key}", code=502, details=str(e))

    def modify_subuser(self, uid: str, subuser: str, **kwargs: Any) -> dict:
        """Modify subuser permissions or attributes."""
        try:
            return self.rgw.modify_subuser(uid=uid, subuser=subuser, **kwargs)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except Exception as e:
            raise CephServiceException(f"Failed to modify subuser {subuser}", code=502, details=str(e))


class CephUserClient:
    """
    User-level client for S3 operations.
    Uses standard S3 protocol and User-scoped Admin API.
    """

    def __init__(self, access_key: str, secret_key: str) -> None:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        self.s3 = session.client(
            "s3",
            endpoint_url=f"http://{consts.CEPH_HOST}:{consts.CEPH_PORT}",
            use_ssl=False,
            config=Config(signature_version="s3v4"),
        )
        self.rgw_user = RGWAdmin(
            access_key=access_key,
            secret_key=secret_key,
            server=f"{consts.CEPH_HOST}:{consts.CEPH_PORT}",
            secure=False,
            verify=False,
        )

    def get_usage_stats(self) -> dict:
        """Fetch usage statistics for the specific user."""
        try:
            return self.rgw_user.request("GET", "/?usage&format=json")
        except rgw_exceptions.AccessDenied:
            raise CephServiceException("Invalid S3 keys or access forbidden", code=401)
        except (req_exceptions.ConnectionError, req_exceptions.Timeout):
            raise CephServiceException("Ceph S3 API connection timeout", code=504)
        except rgw_exceptions.RGWAdminException as e:
            raise CephServiceException(f"User Usage API error: {str(e)}", code=502)
        except Exception as e:
            raise CephServiceException(f"Unexpected User Client error: {str(e)}", code=500)

    def create_bucket(self, bucket_name: str, location_constraint: Optional[str] = None) -> Any:
        """Create a new S3 bucket via Boto3."""
        try:
            bucket_name = bucket_name.replace("_", "-")

            kwargs = {"Bucket": bucket_name}
            if location_constraint:
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": location_constraint}

            return self.s3.create_bucket(**kwargs)

        except self.s3.exceptions.BucketAlreadyExists:
            raise CephServiceException(f"Bucket {bucket_name} already exists", code=409)
        except self.s3.exceptions.BucketAlreadyOwnedByYou:
            raise CephServiceException(f"Bucket {bucket_name} already owned by you", code=200)
        except ClientError as e:
            raise CephServiceException(f"S3 Client Error: {str(e)}", code=400)
        except Exception as e:
            raise CephServiceException(f"Unexpected S3 error", code=500, details=str(e))
