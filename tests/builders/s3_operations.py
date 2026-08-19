from __future__ import annotations

from app.lib.s3.client import CephServiceException
from app.lib.s3.service import CephService
from app.models.s3_user import S3Users, S3UserSchema
from tests.factories.bucket import BucketCreatePayloadFactory, build_bucket_path
from tests.factories.s3_user import ACTIVE_USER_QUOTA, S3UserCreatePayloadFactory


class S3Operations:
    @staticmethod
    def _is_retryable_4xx(exc: CephServiceException) -> bool:
        return 400 <= getattr(exc, "code", 0) < 500

    @classmethod
    def _create_with_retry(cls, create_fn, cleanup_fn):
        try:
            return create_fn()
        except CephServiceException as exc:
            if not cls._is_retryable_4xx(exc):
                raise

            cleanup_fn()
            return create_fn()

    @staticmethod
    def _delete_user_if_exists(name: str) -> None:
        service = CephService()
        existing = service.admin.get_user_info(name)
        if existing:
            try:
                service.admin.remove_user(name)
            except CephServiceException:
                pass

    @staticmethod
    def _delete_bucket_if_exists(*, user_name: str, bucket_name: str) -> None:
        service = CephService()
        bucket_path = build_bucket_path(user_name, bucket_name.replace("_", "-"))

        try:
            bucket = service.get_bucket_by_path(bucket_path)
        except CephServiceException as exc:
            if getattr(exc, "code", None) == 404:
                return
            raise

        S3Operations.delete_bucket(bucket)

    @staticmethod
    def create_user(
        *,
        account,
        pool,
        account_quota,
        short_name: str | None = None,
        owner: str = "owner@example.com",
        quota: dict | None = None,
        description: str | None = None,
    ):
        service = CephService()
        body = S3UserCreatePayloadFactory.build(
            owner=owner,
            account_id=account.id,
            pool_id=pool.id,
            quota=quota if quota is not None else ACTIVE_USER_QUOTA.copy(),
        )
        if short_name is not None:
            body["name"] = short_name
        if description is not None:
            body["description"] = description
        body["name"] = f"{account.name}${body['name']}"

        validated_body = S3UserSchema(
            context={"account_quota": account_quota}
        ).load(body)

        S3Operations._create_with_retry(
            lambda: service.create_s3_user(
                name=validated_body["name"],
                display_name=validated_body["owner"],
                placement=pool.klass,
                quota_data=validated_body["quota"],
            ),
            lambda: S3Operations._delete_user_if_exists(validated_body["name"]),
        )

        validated_body.pop("quota", None)
        s3_user = S3Users(**validated_body)
        s3_user.save()
        service.enrich(s3_user)
        return s3_user

    @staticmethod
    def create_bucket(*, s3_user, name: str | None = None, quota: dict | None = None):
        service = CephService()
        body = BucketCreatePayloadFactory.build()
        if name is not None:
            body["name"] = name
        if quota is not None:
            body["quota"] = quota
        return S3Operations._create_with_retry(
            lambda: service.create_bucket(
                s3_user=s3_user,
                bucket_name=body["name"],
                quota=body["quota"],
            ),
            lambda: S3Operations._delete_bucket_if_exists(
                user_name=s3_user.name,
                bucket_name=body["name"],
            ),
        )

    @staticmethod
    def delete_bucket(bucket) -> None:
        service = CephService()
        try:
            service.delete_s3_bucket(bucket, force=True)
        except CephServiceException:
            pass

    @staticmethod
    def delete_user(s3_user) -> None:
        existing = S3Users.query.filter_by(id=s3_user.id).first()
        if existing is not None:
            try:
                existing.destroy()
            except CephServiceException:
                pass
