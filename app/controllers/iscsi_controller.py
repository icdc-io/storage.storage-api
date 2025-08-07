"""
iSCSI Controller
"""
from datetime import datetime

from flask import abort, jsonify, request
from sqlite3 import IntegrityError
from marshmallow import ValidationError

from app.models.account import Accounts
from app.models.iscsi_quota import IscsiQuotas
from app.models.iscsi_client import IscsiClients, IscsiClientSchema
from app.models.iscsi_config import IscsiConfigs, IscsiConfigSchema
from app.models.iscsi_disk import IscsiDisks, IscsiDiskSchema
from app.models.iscsi_gateway import IscsiGateways, IscsiGatewaySchema
from app.models.snapshot import Snapshots, SnapshotSchema
from app.lib.request_utils import (
    is_failed,
    log,
    no_content,
    abort_detailed,
    request_json,
    parse_jsonapi_filters,
    status_codes,
)


def get_iscsi_limits(subject):
    """
    List account's ISCSI per-pool limit-sets
    """
    limitsets = IscsiQuotas.get_default_limitsets().all()
    # NOTE: currently we do not support non-default limitsets
    limitsets = [limitset.toDict() for limitset in limitsets]
    return jsonify(limitsets)


def set_iscsi_configs(subject):
    """
    Store iSCSI config in Postgres
    """
    body = request_json(request)
    account_name = body.pop("account_name")
    log.debug(
        f"Set iSCSI config to account {account_name} with params {body}"
    )

    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with this name not found.")
    if IscsiConfigs.query.filter_by(account_id=account.id, pool_id=body["pool_id"]).first():
        abort(409, "Config for this pool already exist.")

    body["account_id"] = account.id
    try:
        validated_body = IscsiConfigSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    config = IscsiConfigs(**validated_body)
    config.save()

    if not config.id:
        abort(409, "Config already exist")

    return IscsiConfigSchema().dump(config)


def get_configs(subject):
    """
    Get iSCSI configs from Postgres
    """
    schema = IscsiConfigSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except TypeError:
        abort(400, "Invalid query parameters.")
    configs = IscsiConfigs.filtered(subject).filter_by(**filters).all()
    return jsonify(IscsiConfigSchema(many=True).dump(configs))


def delete_config(subject, config_id):
    """
    Delete iSCSI config
    """
    log.debug(f"Delete config with id {config_id}")
    config_obj = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config_obj:
        abort(404, "Config with this ID not found or you have not permission.")
    config_obj.remove()
    return jsonify("No content.")


def get_config(subject, config_id):
    """
    Get iSCSI Config
    """
    config_obj = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config_obj:
        abort(404, "Config with this ID not found or you have not permission.")
    return IscsiConfigSchema().dump(config_obj)


def set_config_gateway(subject, config_id):
    """
    Set iSCSI gateway to iSCSI target
    """
    body = request_json(request)

    config = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config:
        abort(404, "Config with such id not found or you haven't permission.")

    try:
        validated_body = IscsiGatewaySchema().load(body)
    except ValidationError:
        abort(400, "Invalid input data.")

    validated_body["config_id"] = config_id
    gateway = IscsiGateways(**validated_body)
    config.gateways.append(gateway)

    iscsi_service = config.iscsi_service(ensure_exist=False)
    response = iscsi_service.assign_gateway()

    if is_failed(response):
        abort(response["code"], response["data"])

    gateway.save()
    return IscsiGatewaySchema().dump(gateway)


def get_config_gateways(subject, config_id):
    """
    Get iSCSI Config Gateways
    """
    config = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config:
        abort(404, "Config not found or you haven't permission")

    return jsonify(IscsiGatewaySchema(many=True).dump(config.gateways))


def get_config_disks(subject, config_id):
    """
    Get all iSCSI disks which are assigned to config
    """
    disks = IscsiDisks.filtered(subject).filter_by(config_id=config_id).all()
    return jsonify(IscsiDiskSchema(many=True).dump(disks))


def create_disk(subject, config_id):
    """
    Create iSCSI disk and assign it to iSCSI Config
    """
    body = request_json(request)
    log.debug(
        f"Create disk with params {body} and assign disk to config with id {config_id}"
    )

    snapshot_id = body.pop("from_snapshot_id", None)

    config = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if config is None:
        abort(400, "There is no config with such id or you haven't permission or you haven't permission.")

    quota = IscsiQuotas.query.filter_by(account_id=config.account_id, pool_id=config.pool_id).first()
    if not quota:
        abort(400, "Account doesn't have quota for this pool")

    # Prepare arguments for service call
    # Two flows: simple disk creation and snapshot-based creation
    args = dict()
    if snapshot_id:
        # Snapshot-based disk creation flow
        snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
        if not snapshot:
            abort(404, "Snapshot with this id not found.")

        base_disk = IscsiDisks.filtered(subject).filter_by(id=snapshot.disk_id).first()
        if not base_disk:
            abort(403, "You have not permission for this disk.")

        args.update(
            disk_name=base_disk.name,
            snapshot_name=snapshot.name
        )

        # Set disk size to snapshot size
        body["size_gb"] = snapshot.size_gb

    body["config_id"] = config_id
    try:
        validated_body = IscsiDiskSchema(context={
            "quota": quota
        }).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)
    args.update(body=validated_body)

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    # Select appropriate service method based on mode
    iscsi_service_method = (
        iscsi_service.new_disk_from_snapshot if snapshot_id
        else iscsi_service.create_disk
    )

    response = iscsi_service_method(**args)
    if is_failed(response):
        abort(response["code"], response["data"])

    disk = IscsiDisks(**validated_body)
    disk.save()

    return IscsiDiskSchema().dump(disk)


def update_disk(subject, disk_id):
    """
    Update disk. Resize disk can be only heigher than before resize
    """
    body = request_json(request)

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    config = IscsiConfigs.filtered(subject).filter_by(id=disk.config_id).first()
    if not config:
        abort(404, "Config with this ID not found or you haven't permission.")

    try:
        validated_body = IscsiDiskSchema(
            context={
                'disk': disk,
                'config': config
            }
        ).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    if "size_gb" in validated_body:
        response = iscsi_service.update_disk(disk.name, validated_body)
        if is_failed(response):
            abort(response["code"], response["data"])

    if validated_body.get("owner") != disk.owner and not subject.has_permission("set-owner"):
        validated_body['owner'] = disk.owner  # pylint: disable=multiple-statements
    disk.update(validated_body)

    return IscsiDiskSchema().dump(disk)


def delete_disk(subject, disk_id):
    """
    Delete iSCSI Disk and disconnect it from Config.
    Depends on clients which are assigned to this disk
    """

    log.debug(f"Delete disk with id {disk_id}")

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "There no disk with such id or you haven't permission.")
    if len(disk.clients) != 0:
        abort(409, f"This disk is used by {len(disk.clients)} clients")
    if len(disk.snapshots):
        abort(409, "This disk cannot be deleted. Disk has snapshots.")
    disk.remove()
    return IscsiDiskSchema().dump(disk)


def get_iscsi_clients(subject):
    """
    Get list of iSCSI clients
    """
    schema = IscsiClientSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except TypeError:
        abort(400, "Invalid query parameters.")
    clients = IscsiClients.filtered(subject).filter_by(**filters).all()
    return jsonify(IscsiClientSchema(many=True).dump(clients))


def create_iscsi_client(subject):
    """
    Create iSCSI Client in Ceph and Postgres
    """
    body = request_json(request)
    account_name = body.pop("account_name")
    log.debug(
        f"Create iSCSI client to account {account_name} with params {body}"
    )
    try:
        account_obj = Accounts.filtered(subject).filter_by(name=account_name).first()
        if not account_obj:
            abort(404, "Account with this name not found or you haven't permission.")
        try:
            validated_body = IscsiClientSchema().load(body)
        except ValidationError as e:
            abort_detailed(400, "Invalid parameters", e.messages)

        validated_body["account_id"] = account_obj.id
        client = IscsiClients(**validated_body)
        client.save()
        if client.id is None:
            abort(409, "Can not create client with such IQN")
        return IscsiClientSchema().dump(client)
    except TypeError as exception:
        abort_detailed(400, "Payload is not valid.", str(exception))
    except ValidationError as e:
        abort(400, "Invalid input data.", e.messages)
    except IntegrityError:
        abort(409, "Client with such iqn is already exists")


def update_client(subject, client_id):
    """
    Update Client. Depends on role of requester
    """
    body = request_json(request)

    client = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client:
        abort(404, "Client with this ID not found or you haven't permission.")

    log.debug(f"Update client {client.iqn}.")

    try:
        validated_body = IscsiClientSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    if validated_body.get("owner") != client.owner and not subject.has_permission("set-owner"):
        validated_body["owner"] = client.owner  # pylint: disable=multiple-statements

    for disk in client.disks:
        config = IscsiConfigs.get_by("id", disk.config_id)
        try:
            iscsi_service = config.iscsi_service()
        except ValueError as e:
            abort(400, str(e))

        response = iscsi_service.update_client(client, validated_body)
        if is_failed(response):
            abort(response.get("code", 500), response.get("data", "Internal server error."))

    client.update(validated_body)
    return IscsiClientSchema().dump(client)


def delete_client(subject, client_id):
    """
    Delete Client. Depends on Disks od this client
    """
    log.debug(f"Delete client with id {client_id}")
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client_obj:
        abort(404, "Client with this ID not found or you haven't permission.")
    assigned_disks = len(client_obj.disks)
    if assigned_disks:
        abort(
            409,
            (
                f"Client assigned to {assigned_disks} disks. "
                "Unassign disks before deleting client."
            )
        )
    client_obj.remove()
    return jsonify("No content.")


def get_client_disks(subject, client_id):
    """
    Get clients of disk. Depends on role of requester
    """
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if client_obj is None:
        return abort(404, "There is no client with such ID.")
    return jsonify(IscsiDiskSchema(many=True).dump(client_obj.disks))


def disks_to_client(subject, client_id):
    """
    Connect iSCSI disks to client
    """
    body = request_json(request)
    client = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client:
        abort(404, "Client with this ID not found or you haven't permission.")

    for disk_data in body:
        disk = IscsiDisks.filtered(subject).filter_by(id=disk_data["id"]).first()
        if not disk:
            abort(404, "Disk with this ID does not exist or you don't have permission.")

        if disk in client.disks:
            continue

        config = IscsiConfigs.get_by("id", disk.config_id)

        try:
            iscsi_service = config.iscsi_service()
        except ValueError as e:
            abort(400, str(e))

        _check_clients_quota_exceeds(config)

        response = iscsi_service.assign_disk(client, disk.name)
        if is_failed(response):
            abort(response["code"], response["data"])

        client.disks.append(disk)
        client.save()

    return jsonify(body)


# will be removed after add common quota.
def _check_clients_quota_exceeds(config):
    quota = IscsiQuotas.query.filter_by(account_id=config.account_id, pool_id=config.pool_id).first()
    usage = quota.compute_usage()
    if usage["clients"] + 1 > quota.clients:
        abort(409, "Quota overflow for clients.")


def unassign_client_disk(subject, client_id, disk_id):
    """
    Disconnect an iSCSI disk from a client.
    """
    client = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client:
        abort(404, "Client with this ID not found or you don't have permission.")

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk with this ID not found or you don't have permission.")

    config = IscsiConfigs.get_by("id", disk.config_id)
    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    response = iscsi_service.disconnect_disk(client.iqn, disk.name)

    if is_failed(response):
        abort(response["code"], response["data"])
    client.disks.remove(disk)
    client.save()
    return jsonify("No content.")


def get_disk_snapshots(subject, disk_id):
    """
    Get list of snapshots which are assigned to disk
    """
    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    return jsonify(SnapshotSchema(many=True).dump(disk.snapshots))


def create_disk_snapshot(subject, disk_id):
    """
    Create new snapshot on Ceph side and on Postgres side.
    Assign Snapshot to Disk.
    """
    body = request_json(request)
    log.debug(
        f"Create Snapshot based on disk {disk_id} with params {body}"
    )

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")

    config = IscsiConfigs.filtered(subject).filter_by(
        id=disk.config_id
    ).first()

    try:
        validated_body = SnapshotSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    _check_snapshot_quota_exceed(config)

    response = iscsi_service.create_snapshot(disk_name=disk.name, body=validated_body)
    if is_failed(response):
        abort(response["code"], response["data"])

    for key in ["pool", "disk", "ioctx", "rbd", "image"]:
        validated_body.pop(key, None)
    validated_body["size_gb"] = response["data"]["size"] / 1024**3
    validated_body["creation_time"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    validated_body["disk_id"] = disk_id

    snapshot = Snapshots(**validated_body)
    snapshot.save()

    return SnapshotSchema().dump(snapshot)


def _check_snapshot_quota_exceed(config):
    quota = IscsiQuotas.query.filter_by(pool_id=config.pool_id, account_id=config.account_id).first()
    usage = quota.compute_usage()
    if usage["snapshots"] + 1 > quota.snapshots:
        abort(409, "Quota overflow for snapshots!")


def get_snapshot(subject, disk_id, snapshot_id):
    """
    Get snapshot by id
    """
    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        return abort(404, "Disk hasn't got snapshots")

    return SnapshotSchema().dump(snapshot)


def update_snapshot(subject, disk_id, snapshot_id):
    """
    Update snapshot description
    """
    body = request_json(request)

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")

    config = IscsiConfigs.filtered(subject).filter_by(
        id=disk.config_id
    ).first()

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot not found.")

    try:
        validated_body = SnapshotSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    log.debug(f"Update Snapshot {snapshot.name} with params {validated_body}")

    if validated_body["name"] != snapshot.name:
        response = iscsi_service.update_snapshot(disk_name=disk.name, snapshot_name=snapshot.name, body=validated_body)
        if is_failed(response):
            abort(response["code"], response["data"])

    snapshot.update(validated_body)
    return SnapshotSchema().dump(snapshot)


def delete_snapshot(subject, disk_id, snapshot_id):
    """
    Delete snapshot by name
    """
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot with this ID not found.")
    log.debug(f"Delete snapshot {snapshot.name} from disk with id {disk_id}")

    if not IscsiDisks.filtered(subject).filter_by(id=disk_id).first():
        abort(403, "You have not permission for this disk.")
    snapshot.remove()
    return no_content()


def new_disk_from_snapshot(subject, disk_id, snapshot_name):
    """
    Create disk from snapshot
    """
    body = request_json(request)

    snapshot = Snapshots.filtered(subject).filter_by(name=snapshot_name).first()
    if not snapshot:
        abort(404, "Snapshot with this id not found.")

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(403, "You have not permission for this disk.")

    log.debug(f"Create new Disk based on disk {disk_id}, snapshot {snapshot.name}")

    config = IscsiConfigs.get_by("id", disk.config_id)

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    body["size_gb"] = snapshot.size_gb

    try:
        IscsiDiskSchema(context={"config": config}).load(body)
    except ValidationError as e:
        abort(400, e.messages)

    body["create_image"] = False
    response = iscsi_service.new_disk_from_snapshot(
        disk_name=disk.name,
        snapshot_name=snapshot.name,
        body=body
    )

    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    body["config_id"] = config.id
    body["owner"] = disk.owner
    body.pop("create_image")

    disk = IscsiDisks(**body)
    disk.save()

    return IscsiDiskSchema().dump(disk)


def rollback_snapshot(subject, disk_id, snapshot_name):
    """
    Rollback disk to snapshot
    """

    snapshot = Snapshots.filtered(subject).filter_by(name=snapshot_name).first()
    if not snapshot:
        abort(404, "Snapshot not found.")

    disk = IscsiDisks.filtered(subject).filter_by(id=snapshot.disk_id).first()
    if not disk:
        abort(403, "You have not permission for this disk.")

    log.debug(f"Rollback disk {disk.name} to snapshot {snapshot.name}")

    config = IscsiConfigs.get_by("id", disk.config_id)

    try:
        iscsi_service = config.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    response = iscsi_service.rollback_snapshot(disk_name=disk.name, snapshot_name=snapshot.name)
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    update_params = {"size_gb": response["data"] / 1024**3}
    disk.update(update_params)


def _disk_migrate(body):
    disk = IscsiDisks(**body)
    disk.save()
    return disk.serialize()


def _snapshot_migrate(body):
    snapshot = Snapshots(**body)
    snapshot.save()
    return snapshot.serialize()


def _migrate_assigned_disks(clinet, disk):
    client_obj = IscsiClients.get_by("id", clinet["id"])
    disk_obj = IscsiDisks.get_by("name", disk["disk_name"])
    assigned_disks = client_obj.disks
    assigned_disks.append(disk_obj)
    client_obj.save()
