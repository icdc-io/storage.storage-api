from flask import abort, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.orm import selectinload

from app.lib.request_utils import abort_detailed, parse_jsonapi_filters, request_json
from app.models.account import Accounts
from app.models.s3_quota import S3Quotas, S3QuotaSchema
from app.models.s3_user import S3Users


def index(subject):
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        quotas = S3Quotas.filtered(subject, parsed_filters).options(selectinload(S3Quotas.pool)) \
            .except_(S3Quotas.get_default_limitsets()).all()
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)
    return jsonify(S3QuotaSchema(many=True).dump(quotas))


def create(subject, body=None):
    if not body:
        body = request_json(request)
    account_name = body.pop("account_name", subject.account_name)
    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with this name not found.")
    body["account_id"] = account.id
    try:
        validated_body = S3QuotaSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    if S3Quotas.query.filter_by(account_id=account.id, pool_id=validated_body["pool_id"]).first():
        abort(409, "Only one account quota can be configured for specific pool.")
    quota = S3Quotas(**validated_body)
    account.s3_quotas.append(quota)
    account.save()

    return S3QuotaSchema().dump(quota)


def update(subject, quota_id, body=None):
    if not body:
        body = request_json(request)
    quota = S3Quotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")
    usage = quota.compute_usage()
    schema = S3QuotaSchema(context={"usage": usage}, partial=True)
    try:
        validated_body = schema.load(body | {"pool_id": quota.pool_id})
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters", e.messages)

    quota.update(validated_body)

    return S3QuotaSchema().dump(quota)


def destroy(subject, quota_id):
    quota = S3Quotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")

    if S3Users.query.filter_by(account_id=quota.account_id, pool_id=quota.pool_id).first():
        abort(409, "S3 users must be deleted first.")

    quota.destroy()
    return jsonify("No content.")
