from app.lib.s3.service import CephService
from app.models.s3_user import S3UserStatus
from tests.factories.bucket import UNLIMITED_BUCKET_QUOTA, BucketFactory
from tests.factories.s3_user import (
    DELETED_USER_QUOTA,
    EMPTY_USER_USAGE,
    build_user_state,
)


class FakeS3Ceph:
    def __init__(self):
        self.states = {}
        self.buckets = []
        self.create_user_error = None

    def register_user_state(
        self,
        user,
        *,
        quota=None,
        usage=None,
        status=None,
        keys=None,
    ):
        self.states[user.name] = build_user_state(
            user.name,
            quota=quota if quota is not None else getattr(user, "quota", None),
            usage=usage if usage is not None else getattr(user, "usage", None),
            status=status if status is not None else getattr(user, "status", None),
            keys=keys if keys is not None else getattr(user, "keys", None),
        )
        user.inject_ceph_state(self.states[user.name])
        return self.states[user.name]

    def register_bucket(self, bucket):
        self.buckets.append(bucket)
        return bucket

    def install(self, monkeypatch):
        fake = self

        class FakeAdmin:
            def get_all_buckets_info(self):
                return fake.buckets

            def get_buckets_by_user(self, user_name, **kwargs):
                return [
                    bucket
                    for bucket in fake.buckets
                    if bucket.user_name == user_name
                ]

            def remove_user(self, name):
                fake.states[name] = build_user_state(
                    name,
                    quota=DELETED_USER_QUOTA.copy(),
                    usage=EMPTY_USER_USAGE.copy(),
                )
                fake.states[name]["status"] = S3UserStatus.DELETED

        class FakeCephService(CephService):
            def __init__(self):
                self.admin = FakeAdmin()

            def create_s3_user(self, name, display_name, placement, quota_data):
                if fake.create_user_error is not None:
                    raise fake.create_user_error

                fake.states[name] = build_user_state(
                    name,
                    quota=quota_data.copy(),
                )

            def enrich(self, users):
                if not users:
                    return

                if isinstance(users, list):
                    for user in users:
                        self._enrich_user(user)
                    return

                self._enrich_user(users)

            def _enrich_user(self, user):
                state = fake.states.get(
                    user.name,
                    build_user_state(
                        user.name,
                        quota=getattr(user, "quota", None),
                    ),
                )
                user.inject_ceph_state(state)

            def update_s3_user(self, s3_user, owner=None, quota=None, status=None):
                current = fake.states.get(
                    s3_user.name,
                    build_user_state(
                        s3_user.name,
                        quota=getattr(s3_user, "quota", None),
                    ),
                )
                next_quota = current["quota"].copy()
                if quota:
                    next_quota.update(quota)

                next_status = status or current["status"]
                fake.states[s3_user.name] = build_user_state(
                    s3_user.name,
                    quota=next_quota,
                )
                fake.states[s3_user.name]["status"] = next_status
                s3_user.inject_ceph_state(fake.states[s3_user.name])
                return fake.states[s3_user.name]

            def create_bucket(self, s3_user, bucket_name, quota):
                bucket = BucketFactory.build(
                    s3_user=s3_user,
                    name=bucket_name,
                    quota=quota or UNLIMITED_BUCKET_QUOTA.copy(),
                )
                fake.buckets.append(bucket)
                return bucket

            def get_bucket_by_path(self, path):
                for bucket in fake.buckets:
                    if bucket.path == path:
                        return bucket

                from app.lib.s3.exceptions import CephServiceException

                raise CephServiceException("missing", code=404)

            def update_bucket(self, bucket, quota_update):
                updated_bucket = BucketFactory.build(
                    name=bucket.name,
                    path=bucket.path,
                    user_name=bucket.user_name,
                    quota=bucket.quota | quota_update,
                    usage=bucket.usage,
                )
                for index, stored_bucket in enumerate(fake.buckets):
                    if stored_bucket.path == bucket.path:
                        fake.buckets[index] = updated_bucket
                        break
                return updated_bucket

        monkeypatch.setattr("app.controllers.s3_controller.CephService", FakeCephService)
        monkeypatch.setattr("app.lib.s3.service.CephService", FakeCephService)
        monkeypatch.setattr("app.lib.s3.service.CephAdminClient", FakeAdmin)
        return self
