"""
iSCSI Controller
"""
from datetime import datetime
from sqlite3 import IntegrityError

from flask import abort, jsonify, request
from marshmallow import ValidationError

from app.lib.request_utils import (
    abort_detailed,
    is_failed,
    is_fake,
    log,
    no_content,
    parse_jsonapi_filters,
    request_json,
    status_codes,
)
from app.models.account import Accounts
from app.models.iscsi_client import IscsiClients, IscsiClientSchema
from app.models.iscsi_cluster import IscsiClusters, IscsiClusterSchema
from app.models.iscsi_disk import IscsiDisks, IscsiDiskSchema
from app.models.iscsi_gateway import IscsiGateways, IscsiGatewaySchema
from app.models.iscsi_quota import IscsiQuotas
from app.models.iscsi_target import IscsiTargets
from app.models.pool import Pools
from app.models.snapshot import Snapshots, SnapshotSchema


def get_iscsi_limits(subject):
    """
    List account's ISCSI per-pool limit-sets
    """
    limitsets = IscsiQuotas.get_default_limitsets().all()
    # NOTE: currently we do not support non-default limitsets
    limitsets = [limitset.to_dict(is_limit=True) for limitset in limitsets]
    return jsonify(limitsets)


def create_cluster(subject, body=None):
    """
    Create iSCSI cluster in Postgres
    """
    if not body:
        body = request_json(request)
    account_name = body.pop("account_name", subject.account_name)
    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with this name not found or you haven't permission.")
    log.debug(
        f"Set iSCSI cluster to account {account_name} with params {body}"
    )

    body["account_id"] = account.id
    try:
        validated_body = IscsiClusterSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)
    cluster = IscsiClusters(**validated_body)
    cluster.save()

    if not cluster.id:
        abort(409, "Config already exist")

    return cluster.to_dict()


def get_clusters(subject):
    """
    List iSCSI clusters from Postgres
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        clusters = IscsiClusters.filtered(subject, request_filters=parsed_filters).all()
    except ValidationError as e:
        abort(400, e.messages)
    return jsonify(IscsiClusters.to_dict_many(clusters))


def delete_cluster(subject, cluster_id):
    """
    Delete iSCSI config
    """
    log.debug(f"Delete config with id {cluster_id}")
    cluster = IscsiClusters.filtered(subject).filter_by(id=cluster_id).first()
    if not cluster:
        abort(404, "Config with this ID not found or you have not permission.")
    cluster.destroy()
    return jsonify("No content.")


def get_cluster(subject, cluster_id):
    """
    Get iSCSI Cluster
    """
    cluster = IscsiClusters.filtered(subject).filter_by(id=cluster_id).first()
    if not cluster:
        abort(404, "Config with this ID not found or you have not permission.")
    return cluster.to_dict()


def _create_target(subject, account, body):
    """
    Internal helper to create a target.
    """
    cluster_name = body.get("cluster_name")
    cluster = None

    if cluster_name:
        cluster = IscsiClusters.filtered(subject).filter_by(name=cluster_name).first()

    if not cluster:
        cluster = account.get_least_loaded_cluster()

    if not cluster:
        abort(404, f"No suitable cluster found for account {account.name}")

    pool = Pools.get_by("id", body.get("pool_id", None))
    if not pool:
        abort(404, "Pool with this ID not found.")

    if IscsiTargets.get_target(cluster.account_id, pool.id):
        abort(409, "Target for this pool already exist in this account.")

    log.debug(f"Creating Target for account {account.id} on cluster {cluster.id} for pool {pool.name}")

    target_params = {"pool_id": pool.id, "cluster_id": cluster.id}
    target = IscsiTargets(**target_params)
    target.save()

    if not target.id:
        abort(500, "Unexpected error: Target was not saved.")

    return no_content()


# def delete_target(subject, target_id):
#     target = IscsiTargets.filtered(subject).filter_by(id=target_id).first()
#     if not target:
#         abort(404, "Target with this ID not found or you have not permission.")
#     target.destroy()
#     return no_content()


def create_gateway(subject, body=None):
    """
    Set iSCSI gateway to iSCSI Cluster
    """
    if not body:
        body = request_json(request)
    log.info("Start process of create iSCSI Gateway")
    cluster_id = body.get("cluster_id")
    cluster = IscsiClusters.filtered(subject).filter_by(id=cluster_id).first()
    if not cluster:
        abort(404, "Cluster with such id not found or you haven't permission.")

    try:
        validated_body = IscsiGatewaySchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    gateway = IscsiGateways(**validated_body)
    gateway.save()
    if not gateway.id:
        abort(409, "Can not create gateway in database.")
    return no_content()


def delete_gateway(subject, gateway_id):
    """
    Delete iSCSI gateway from iSCSI Cluster
    """
    gateway = IscsiGateways.filtered(subject).filter_by(id=gateway_id).first()
    if not gateway:
        abort(404, "Gateway with such id not found or you haven't permission.")
    gateway.destroy()
    return gateway.to_dict()


def get_disks(subject):
    """
    Get all iSCSI disks which are assigned to config
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        disks = IscsiDisks.filtered(subject, request_filters=parsed_filters).all()
    except ValidationError as e:
        abort(400, e.messages)
    return jsonify(IscsiDisks.to_dict_many(disks))


def create_disk(subject):
    """
    Create iSCSI disk and assign it to iSCSI Config
    """
    body = request_json(request)
    log.debug(
        f"Create disk with params {body} for pool {body['pool_id']}"
    )

    snapshot_id = body.pop("from_snapshot_id", None)
    account_name = body.pop("account_name", subject.account_name)

    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, f"Account {account_name} not found or you haven't permission.")

    target = IscsiTargets.get_target(account.id, body.pop("pool_id"))
    if target is None:
        abort(404, "There is no target with such id or you haven't permission.")

    quota = IscsiQuotas.query.filter_by(account_id=target.account.id, pool_id=target.pool_id).first()
    if not quota:
        abort(404, "Account doesn't have quota for this pool")

    # Prepare arguments for service call
    # Two flows: simple disk creation and snapshot-based creation
    args = dict()
    if snapshot_id:
        # Snapshot-based disk creation flow
        snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
        if not snapshot:
            abort(404, "Snapshot with this id not found.")
        base_disk = snapshot.disk
        args.update(
            disk_name=base_disk.name,
            snapshot_name=snapshot.name
        )

        # Set disk size to snapshot size
        body["size_gb"] = snapshot.size_gb
    body["target_id"] = target.id
    try:
        validated_body = IscsiDiskSchema(context={
            "quota": quota
        }).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)
    args.update(body=validated_body)

    if not is_fake():
        try:
            iscsi_service = target.iscsi_service()
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
    try:
        validated_body = IscsiDiskSchema(
            context={
                'disk': disk,
            },
            partial=True
        ).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    if not is_fake() and "size_gb" in validated_body:
        try:
            iscsi_service = disk.target.iscsi_service()
        except ValueError as e:
            abort(400, str(e))

        response = iscsi_service.update_disk(disk.name, validated_body)
        if is_failed(response):
            abort(response["code"], response["data"])

    if body.get("owner", None) and "set-owner" not in subject.policy["iscsi.disks"]["permissions"]:
        del validated_body["owner"]  # pylint: disable=multiple-statements
    disk.update(validated_body)

    return disk.to_dict()


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
    disk.destroy()
    return IscsiDiskSchema().dump(disk)


def get_clients(subject):
    """
    Get list of iSCSI clients
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        clients = IscsiClients.filtered(subject, parsed_filters).all()
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)
    return jsonify(IscsiClients.to_dict_many(clients))


def create_client(subject):
    """
    Create iSCSI Client in Ceph and Postgres
    """
    body = request_json(request)
    account_name = body.pop("account_name", subject.account_name)
    log.debug(
        f"Create iSCSI client to account {account_name} with params {body}"
    )
    try:
        account = Accounts.filtered(subject).filter_by(name=account_name).first()
        if not account:
            abort(404, "Account with this name not found or you haven't permission.")

        body["account_id"] = account.id
        try:
            validated_body = IscsiClientSchema().load(body)
        except ValidationError as e:
            abort_detailed(400, "Invalid parameters", e.messages)

        client = IscsiClients(**validated_body)
        client.save()
        if client.id is None:
            abort(409, "Can not create client with such IQN")
        return client.to_dict()
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
        validated_body = IscsiClientSchema(partial=True).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    if body.get("owner", None) and "set-owner" not in subject.policy["iscsi.clients"]["permissions"]:
        del validated_body["owner"]  # pylint: disable=multiple-statements

    if not is_fake():
        for disk in client.disks:
            try:
                iscsi_service = disk.target.iscsi_service()
            except ValueError as e:
                abort(400, str(e))

            response = iscsi_service.update_client(client, validated_body)
            if is_failed(response):
                abort(response.get("code", 500), response.get("data", "Internal server error."))

    client.update(validated_body)
    return client.to_dict()


def delete_client(subject, client_id):
    """
    Delete Client. Depends on Disks od this client
    """
    log.debug(f"Delete client with id {client_id}")
    client = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client:
        abort(404, "Client with this ID not found or you haven't permission.")
    assigned_disks = len(client.disks)
    if assigned_disks:
        abort(
            409,
            (
                f"Client assigned to {assigned_disks} disks. "
                "Unassign disks before deleting client."
            )
        )
    client.destroy()
    return jsonify("No content.")


# TODO EK: may be replace by just get client
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

        if disk.account_id != client.account_id:
            abort(400, "Disk and client belong to different accounts.")

        if disk in client.disks:
            continue

        _check_clients_quota_exceeds(disk.target)

        if not is_fake():
            try:
                iscsi_service = disk.target.iscsi_service()
            except ValueError as e:
                abort(400, str(e))

            response = iscsi_service.assign_disk(client, disk.name)
            if is_failed(response):
                abort(response["code"], response["data"])

        client.disks.append(disk)
        client.save()

    return jsonify(body)


# will be removed after add common quota.
def _check_clients_quota_exceeds(target):
    quota = IscsiQuotas.query.filter_by(account_id=target.account.id, pool_id=target.pool_id).first()
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
    if not is_fake():
        try:
            iscsi_service = disk.target.iscsi_service()
        except ValueError as e:
            abort(400, str(e))

        response = iscsi_service.disconnect_disk(client.iqn, disk.name)

        if is_failed(response):
            abort(response["code"], response["data"])

    if disk in client.disks:
        client.disks.remove(disk)
        client.save()

    return jsonify("No content.")


def get_snapshots(subject):
    """
    Get list of snapshots which are assigned to disk
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        snapshots = Snapshots.filtered(subject, parsed_filters).all()
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)

    return jsonify(Snapshots.to_dict_many(snapshots))


def create_snapshot(subject):
    """
    Create new snapshot on Ceph side and on Postgres side.
    Assign Snapshot to Disk.
    """
    body = request_json(request)
    log.debug(
        f"Create Snapshot based on disk {body['disk_id']} with params {body}"
    )

    disk = IscsiDisks.filtered(subject).filter_by(id=body.get("disk_id")).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")

    try:
        validated_body = SnapshotSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    try:
        iscsi_service = disk.target.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    _check_snapshot_quota_exceed(disk.target)

    response = iscsi_service.create_snapshot(disk_name=disk.name, body=validated_body)
    if is_failed(response):
        abort(response["code"], response["data"])

    for key in ["pool", "disk", "ioctx", "rbd", "image"]:
        validated_body.pop(key, None)
    validated_body["size_gb"] = response["data"]["size"] / 1024**3
    validated_body["creation_time"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    snapshot = Snapshots(**validated_body)
    snapshot.save()

    return SnapshotSchema().dump(snapshot)


def _check_snapshot_quota_exceed(target):
    quota = IscsiQuotas.query.filter_by(pool_id=target.pool_id, account_id=target.account.id).first()
    usage = quota.compute_usage()
    if usage["snapshots"] + 1 > quota.snapshots:
        abort(409, "Quota overflow for snapshots!")


def get_snapshot(subject, snapshot_id):
    """
    Get snapshot by id
    """
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        return abort(404, "Disk hasn't got snapshots")

    return SnapshotSchema().dump(snapshot)


def update_snapshot(subject, snapshot_id):
    """
    Update snapshot description
    """
    body = request_json(request)

    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot not found.")

    try:
        validated_body = SnapshotSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid input data.", e.messages)

    try:
        iscsi_service = snapshot.target.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    log.debug(f"Update Snapshot {snapshot.name} with params {validated_body}")

    if validated_body.get("name", None) and validated_body["name"] != snapshot.name:
        response = iscsi_service.update_snapshot(disk_name=snapshot.disk.name, snapshot_name=snapshot.name, body=validated_body)
        if is_failed(response):
            abort(response["code"], response["data"])

    snapshot.update(validated_body)
    return SnapshotSchema().dump(snapshot)


def delete_snapshot(subject, snapshot_id):
    """
    Delete snapshot by name
    """
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot with this ID not found.")

    log.debug(f"Delete snapshot {snapshot.name} from disk with id {snapshot.disk_id}")
    snapshot.destroy()
    return no_content()


def rollback_snapshot(subject, snapshot_id):
    """
    Rollback disk to snapshot
    """
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot not found.")

    log.debug(f"Rollback disk {snapshot.disk.name} to snapshot {snapshot.name}")

    try:
        iscsi_service = snapshot.target.iscsi_service()
    except ValueError as e:
        abort(400, str(e))

    response = iscsi_service.rollback_snapshot(disk_name=snapshot.disk.name, snapshot_name=snapshot.name)
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    update_params = {"size_gb": response["data"] / 1024**3}
    snapshot.disk.update(update_params)
    return IscsiDiskSchema().dump(snapshot.disk)


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
