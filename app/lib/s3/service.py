"""
Ceph S3 Service Provider.
Responsible for orchestrating RGW Admin API and S3 User API calls to aggregate
user/bucket states, quotas, and usage metrics.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

from app import consts
from app.lib.s3.client import (
    BotoClient,
    CephAdminClient,
    CephServiceException,
    CephUserClient,
)
from app.loggers import log
from app.models.bucket import Bucket
from app.models.s3_user import S3Users, S3UserStatus


class CephService:
    def __init__(self):
        self.admin = CephAdminClient()

    def enrich(self, users: Union[List[S3Users], S3Users]) -> None:
        """
        Injects Ceph metadata and usage into S3Users model instances.
        Supports both a single object and a list for batch processing.
        """
        if not users:
            return

        if isinstance(users, list):
            count = len(users)
            start_time = time.perf_counter()

            names = [u.name for u in users]
            names_str = ", ".join(names[:30]) + ("..." if count > 30 else "")

            log.info(f"Enriching {count} S3 users: [{names_str}]")

            user_states = self.get_users_states(names)

            for user in users:
                state = user_states.get(user.name)
                user.inject_ceph_state(state)

            duration = time.perf_counter() - start_time
            log.info(f"Successfully enriched {count} users in {duration:.2f}s")
            return

        log.info(f"Enriching single user: {users.name}")
        user_state = self.get_user_state(users.name)
        users.inject_ceph_state(user_state)

    def get_user_state(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch and assemble state for a single user."""
        log.info(f"Fetch state for user {name}")
        metadata = self.admin.get_user_info(name)
        if not metadata:
            log.warning(f"Metadata not found for user: {name}")
            return None

        usage = self._fetch_user_usage(metadata)
        return self._assemble_user_state(metadata, usage)

    def get_users_states(self, names: Union[List[str], str]) -> Dict[str, Dict[str, Any]]:
        """Maps user_names to their respective assembled states."""
        if not names:
            return {}

        if isinstance(names, str):
            return {names: self.get_user_state(names)}

        log.debug(f"Fetching states for batch: {names}")
        return self._get_multiple_users_states(names)

    def _get_multiple_users_states(self, names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Concurrently fetches and assembles states for multiple users.
        Optimizes performance by parallelizing usage calculations which involve network I/O.
        """
        # First, batch fetch basic metadata (admin info) for all requested names
        indexed_metadata = self._fetch_users_metadata(names)

        result = {}
        users_usage = {}

        log.debug(f"Executing parallel s3 user usage fetch for {len(names)} users")
        # ThreadPoolExecutor is used because usage fetching is an I/O bound task
        with ThreadPoolExecutor(max_workers=consts.CEPH_MAX_WORKERS) as executor:
            future_to_name = {}

            for name in names:
                metadata = indexed_metadata.get(name)

                if metadata:
                    # Submit heavy 'usage' calculation to a separate thread
                    f = executor.submit(self._fetch_user_usage, metadata)
                    future_to_name[f] = name
                else:
                    # If metadata is missing, immediately mark as empty/deleted state
                    result[name] = {}

            # Wait for all submitted threads to finish and collect results
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                # Store the calculated usage stats indexed by username
                users_usage[name] = future.result()
        log.debug("Successfully fetch all metadata for users")

        log.debug("Build state dictionary for s3 users.")
        # Final step: Merge metadata and calculated usage into a standard response format
        for name, metadata in indexed_metadata.items():
            if name in names and metadata:
                # Combine everything using our assembly helper
                result[name] = self._assemble_user_state(
                    metadata,
                    users_usage.get(name)
                )

        return result

    def _build_user_name_by_metadata(self, metadata: Dict[str, Any]) -> str:
        """Constructs the full Ceph UID (tenant$user_id)."""
        uid = metadata.get("user_id")
        tenant = metadata.get("tenant", "")
        return f"{tenant}${uid}" if tenant else uid

    def _fetch_users_metadata(self, names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetches raw user metadata from the RGW Admin API.
        Uses multi-threading to bypass the latency of sequential HTTP requests.
        """
        log.debug(f"Executing parallel RGW metadata fetch for {len(names)} users")

        # Use executor.map to trigger multiple 'get_user_info' calls in parallel.
        # This returns results in the same order as the 'names' list.
        with ThreadPoolExecutor(max_workers=consts.CEPH_MAX_WORKERS) as executor:
            raw_results = list(executor.map(self.admin.get_user_info, names))

        indexed_metadata = {}

        # Process successful responses and index them by their full Ceph UID (tenant$user)
        for info in raw_results:
            if info:
                # Reconstruct the key name because Ceph metadata contains the canonical UID
                name = self._build_user_name_by_metadata(info)
                indexed_metadata[name] = info

        # Ensure every requested name has an entry in the result.
        # If a user wasn't found in Ceph, we provide an empty dict as a placeholder.
        for name in names:
            if name not in indexed_metadata:
                indexed_metadata[name] = {}

        log.debug("Successfully fetch all metadata for users")
        return indexed_metadata

    def _fetch_user_usage(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        """
        Tries to fetch usage via CephUserClient.
        """
        if not metadata:
            # Logic if user is deleted.
            return {}

        username = self._build_user_name_by_metadata(metadata)
        is_suspended = metadata.get("suspended", False)
        s3_keys = metadata.get("keys", [{}])[0] if metadata.get("keys") else {}

        access_key = s3_keys.get("access_key")
        secret_key = s3_keys.get("secret_key")

        if not is_suspended and access_key and secret_key:
            # Logic if user is active
            user_client = CephUserClient(access_key, secret_key)
            raw = user_client.get_usage_stats()

            summary = raw.get('Summary', [0]*8)
            capacity = raw.get('CapacityUsed', [{}])
            buckets_count = len(capacity[0].get('Buckets', [])) if capacity else 0

            return {
                "data_size_mb": summary[6] // (1024**2) if len(summary) > 6 else 0,
                "objects": summary[7] if len(summary) > 7 else 0,
                "buckets": buckets_count
            }

        # Logic if user is locked.
        # Sum usage of each bucket in user.
        buckets_info = self.admin.get_buckets_by_user(username)
        size_kb = 0
        objs = 0

        for b in buckets_info:
            main = b.get("usage", {}).get("rgw.main", {})
            size_kb += main.get("size_actual", 0)
            objs += main.get("num_objects", 0)

        return {
            "data_size_mb": size_kb // (1024**2),
            "objects": objs,
            "buckets": len(buckets_info)
        }

    def _assemble_user_state(self, metadata: Dict[str, Any], usage: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """
        Transforms raw Ceph metadata and calculated usage into a standardized S3 user state.

        This is a helper method that maps RGW Admin API response fields to the internal
        application schema, ensuring consistent data types for status, keys, and quotas.
        """
        if not metadata:
            return {}

        quota_info = metadata.get("user_quota", {})
        quota_data = {
            "data_size_mb": quota_info.get("max_size_kb", 0) // 1024,
            "objects": quota_info.get("max_objects", 0),
            "buckets": metadata.get("max_buckets", 0)
        }

        return {
            "status": S3UserStatus.LOCKED if metadata.get("suspended") else S3UserStatus.ACTIVE,
            "usage": usage,
            "keys": {
                "s3": metadata.get("keys", [{}])[0] if metadata.get("keys") else {},
                "swift": metadata.get("swift_keys", [{}])[0] if metadata.get("swift_keys") else {}
            },
            "quota": quota_data
        }

    def create_s3_user(
        self,
        name: str,
        display_name: str,
        placement: str,
        quota_data: Dict[str, Any]
    ) -> None:
        """
        Orchestrates the full creation process for a new S3 user in Ceph.

        This includes RGW account initialization, quota enforcement,
        placement tag synchronization, and Swift subuser provisioning.
        """
        log.info(f"Starting creation process for S3 user: {name} (Placement: {placement})")

        # 1. Primary RGW User creation
        self.admin.create_rgw_user(
            name=name,
            display_name=display_name,
            placement=placement,
            max_buckets=quota_data.get("buckets", 0)
        )
        log.debug(f"RGW user base account created for {name}")

        # 2. Quota configuration (Size and Object quotas)
        data_size_mb = int(quota_data.get("data_size_mb", 0))
        objects = int(quota_data.get("objects", 0))

        self.admin.set_user_quota(
            name=name,
            data_size_mb=data_size_mb,
            objects=objects
        )
        log.debug(f"Quotas set for {name}: {data_size_mb}MB, {objects} objects")

        # 3. Placement tag synchronization for storage policies
        self.admin.update_user_placement_tags(uid=name, tags=placement)
        log.debug(f"Placement tags synchronized for {name}")

        # 4. Swift protocol support initialization
        self.admin.create_swift_subuser(name=name)
        log.debug(f"Swift subuser created for {name}")

        log.info(f"S3 user {name} successfully provisioned with all sub-resources")

    def remove_s3_user(self, user):
        """
        Remove S3 user.
        """
        self.admin.remove_user(user.name)

    def update_s3_user(
        self,
        s3_user,
        owner: str = None,
        quota: dict = None,
        status: str = None
    ):
        """
        Updates S3 user attributes and quotas by synchronizing local model changes with Ceph.
        """
        log.info(f"Initiating update for S3 user: {s3_user.name}")
        update_params = {}

        if owner and s3_user.owner != owner:
            update_params["display_name"] = owner

        if status:
            is_suspended = (status == S3UserStatus.LOCKED)
            if s3_user.status != status:
                s3_user.status = status
                update_params["suspended"] = is_suspended

        if quota:
            s3_user.quota.update({
                k: int(v) for k, v in quota.items()
                if k in ["data_size_mb", "objects", "buckets"]
            })
            if "buckets" in quota:
                update_params["max_buckets"] = s3_user.quota["buckets"]

        if update_params:
            log.debug(f"Applying metadata updates to Ceph for {s3_user.name}: {list(update_params.keys())}")
            self.admin.modify_user(uid=s3_user.name, **update_params)

        if quota and ("data_size_mb" in quota or "objects" in quota):
            log.debug(f"Applying storage quota updates to Ceph for {s3_user.name}")
            self.admin.set_user_quota(
                name=s3_user.name,
                data_size_mb=s3_user.quota["data_size_mb"],
                objects=s3_user.quota["objects"]
            )
        log.info(f"Update completed successfully for user: {s3_user.name}")
        return self.get_users_states(s3_user.name).get(s3_user.name)

    def create_bucket(self, s3_user, bucket_name: str, quota: dict):
        """
        Creates a new S3 bucket for a user and applies specified quotas.
        """
        if quota is None:
            quota = {}

        log.info(f"Initiating bucket creation: {bucket_name} for user {s3_user.name}")

        # Pre-creation check: avoid duplicate names for this user
        if bucket_name in self.admin.get_buckets_by_user(s3_user.name, stats=False):
            raise CephServiceException("Bucket already exist", code=400)
        s3_keys = s3_user.keys.get("s3", {})

        # Credential validation
        if not s3_keys.get("access_key") or not s3_keys.get("secret_key"):
            raise CephServiceException("User has no S3 keys", code=400)

        user_client = BotoClient(s3_keys["access_key"], s3_keys["secret_key"])
        constraint = s3_user.pool.location_constraint() if "$" in s3_user.name else None

        log.debug(f"Provisioning bucket {bucket_name} (Constraint: {constraint})")
        user_client.create_bucket(bucket_name, location_constraint=constraint)

        data_size_mb = quota.get("data_size_mb", -1)
        objects = quota.get("objects", -1)

        log.debug(f"Applying quota to {bucket_name}: {data_size_mb}MB, {objects} objects")
        self.admin.set_bucket_quota(
            uid=s3_user.name,
            bucket_name=bucket_name.replace("_", "-"),
            data_size_mb=data_size_mb,
            objects=objects
        )

        log.info(f"Bucket {bucket_name} successfully created and configured for {s3_user.name}")

        return self.get_bucket_state(user_name=s3_user.name, bucket_name=bucket_name)

    def get_bucket_by_path(self, path: str):
        """
        Retrieves bucket state directly using its Ceph path (tenant/bucket_name).
        """
        log.debug(f"Fetching bucket state for path: {path}")
        metadata = self.admin.get_bucket_info(path)
        return self._assemble_bucket_state(metadata)

    def get_bucket_state(self, user_name: str, bucket_name: str):
        """
        Constructs the Ceph path and retrieves bucket information.
        """
        bucket_name = bucket_name.replace("_", "-")
        tenant = user_name.split('$')[0] if '$' in user_name else None
        path = f"{tenant}/{bucket_name}" if tenant else bucket_name

        return self.get_bucket_by_path(path)

    def _assemble_bucket_state(self, metadata: dict) -> Any:
        """
        Transforms raw RGW bucket metadata into a standardized Bucket model.
        Calculates usage metrics and formats quota information.
        """
        usage_info = metadata.get("usage", {})
        main = usage_info.get("rgw.main", {})
        multimeta = usage_info.get("rgw.multimeta", {})

        objects = main.get("num_objects", 0)
        multipart = multimeta.get("num_objects", 0)

        usage_data = {
            "data_size_mb": main.get("size_actual", 0) // (1024 ** 2),
            "total_objects": objects + multipart,
            "objects": objects,
            "multipart_objects": multipart
        }

        raw_quota = metadata.get("bucket_quota", {})
        max_size = raw_quota.get("max_size", -1)

        quota_data = {
            "data_size_mb": -1 if max_size < 0 else max_size // (1024 * 1024),
            "objects": raw_quota.get("max_objects", -1)
        }

        bucket_name = metadata.get("bucket", "")
        tenant = metadata.get("tenant", "")

        return Bucket(
            path=f"{tenant}/{bucket_name}" if tenant else bucket_name,
            name=bucket_name,
            user_name=metadata.get("owner"),
            quota=quota_data,
            usage=usage_data
        )

    def list_s3_buckets(self, s3_users: list, filters: dict = None) -> list:
        """
        Lists all S3 buckets for a given list of users, with optional filtering.
        Optimizes by choosing between user-specific fetch or global cluster fetch.
        """
        if not s3_users:
            return []

        user_names = [u.name for u in s3_users]

        log.info(f"Listing buckets for {len(s3_users)} users. Filters: {list(filters.keys()) if filters else 'None'}")

        if len(s3_users) == 1:
            raw_buckets = self.admin.get_buckets_by_user(s3_users[0].name)
        else:
            raw_buckets = self.admin.get_all_buckets_info()

        buckets = []
        for info in raw_buckets:
            bucket = self._assemble_bucket_state(info)

            if bucket.user_name in user_names:
                if not filters or self._apply_filters(bucket, filters):
                    buckets.append(bucket)

        log.info(f"Successfully listed {len(buckets)} filtered buckets")

        return buckets

    def _apply_filters(self, bucket, filters: dict) -> bool:
        data = bucket.to_dict()
        for key, value in filters.items():
            if str(data.get(key)) != str(value):
                return False
        return True

    def update_bucket(self, bucket, quota_update: dict):
        """
        Updates the quota configuration for an existing S3 bucket.
        Synchronizes local updates with Ceph and returns the refreshed bucket state.
        """
        log.info(f"Updating quota for bucket {bucket.path}")

        new_size_mb = quota_update.get("data_size_mb", bucket.quota["data_size_mb"])
        new_objects = quota_update.get("objects", bucket.quota["objects"])

        log.debug(f"New quota for {bucket.name}: {new_size_mb}MB, {new_objects} objects")

        self.admin.set_bucket_quota(
            uid=bucket.user_name,
            bucket_name=bucket.name,
            data_size_mb=new_size_mb,
            objects=new_objects
        )

        log.info(f"Bucket {bucket.name} quota updated successfully")
        return self.get_bucket_state(bucket.user_name, bucket.name)

    def delete_s3_bucket(self, bucket, force: bool = True):
        """
        Removes an S3 bucket from the Ceph.
        """
        log.warning(f"Deleting bucket {bucket.path} (Force purge: {force})")

        self.admin.remove_bucket(bucket.path, purge=force)

        log.info(f"Bucket {bucket.path} deleted successfully")
        return True

    def regenerate_user_keys(self, s3_user):
        """
        Regenerate S3 and Swift credentials for the user.
        Generates new keys, removes the old S3 access key, and refreshes the user model.
        """
        log.info(f"Initiating key rotation for user: {s3_user.name}")

        old_keys = s3_user.keys

        log.debug(f"Generating new S3 keys for {s3_user.name}")
        self.admin.modify_user(uid=s3_user.name, generate_key=True)

        log.debug(f"Generating new Swift secret for {s3_user.name}:swift")
        self.admin.modify_subuser(
            uid=s3_user.name,
            subuser=s3_user.name+":swift",
            access="full",
            generate_secret=True
        )

        access_key = old_keys.get("s3").get("access_key")
        if access_key:
            log.debug(f"Removing old access key: {access_key[:4]}****")
            self.admin.remove_key(uid=s3_user.name, access_key=access_key)

        log.info(f"Key rotation completed for {s3_user.name}. Re-enriching model...")
        self.enrich(s3_user)
