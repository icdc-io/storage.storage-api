from flask import abort, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.orm import selectinload

from app.controllers.iscsi_controller import _create_target
from app.lib.request_utils import (
    abort_detailed,
    log,
    parse_jsonapi_filters,
    request_json,
)
from app.models.account import Accounts
from app.models.iscsi_quota import (
    IscsiQuotaResponseSchema,
    IscsiQuotas,
    IscsiQuotaSchema,
)
from app.models.iscsi_target import IscsiTargets


def get_account_quotas(subject):
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        quotas = IscsiQuotas.filtered(subject, parsed_filters).options(selectinload(IscsiQuotas.pool)) \
            .except_(IscsiQuotas.get_default_limitsets()).all()
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)
    return jsonify(IscsiQuotaResponseSchema(many=True).dump(quotas))


def create(subject, body=None):
    if not body:
        body = request_json(request)

    account_name = body.pop("account_name", subject.account_name)
    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with this name not found or you haven't permission")

    log.debug(f"Set iSCSI quota to account {account_name} with params {body}")

    target_body = body.pop("target", {})
    body["account_id"] = account.id

    try:
        validated_body = IscsiQuotaSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    if IscsiQuotas.query.filter_by(account_id=account.id, pool_id=validated_body["pool_id"]).first():
        abort(409, "Quota for this pool already exists.")

    target_body["pool_id"] = validated_body["pool_id"]
    _create_target(subject, account, target_body)

    quota = IscsiQuotas(**validated_body)
    quota.save()

    return quota.to_dict()


def update(subject, quota_id, body=None):
    if not body:
        body = request_json(request)
    quota = IscsiQuotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")
    schema = IscsiQuotaSchema(context={"usage": quota.compute_usage()}, partial=True)
    try:
        validated_body = schema.load(body | {"pool_id": quota.pool_id})
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    quota.update(validated_body)
    return quota.to_dict()


def destroy(subject, quota_id):
    quota = IscsiQuotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")

    if quota.target:
        quota.target.destroy()

    quota.destroy()
    return jsonify("No content.")
