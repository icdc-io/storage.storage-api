"""
iSCSI Router module
"""
from flask import Blueprint, request

import app.controllers.auth as auth
from app.controllers import iscsi_controller as controller
from app.lib.request_utils import process_response, request_json, handle_exception
from app.controllers.iscsi import quotas_controller
from werkzeug.exceptions import HTTPException

iscsi = Blueprint(name="iscsi", import_name=__name__)
iscsi.register_error_handler(HTTPException, handle_exception)


@iscsi.route("/limits", methods=["GET"])
@auth.account_auth_required
def get_iscsi_limits(*args, **kwargs):
    return controller.get_iscsi_limits(**kwargs), 200


@iscsi.route("/quotas", methods=["GET"])
@auth.account_auth_required
def get_account_iscsi_quota(*args, **kwargs):
    return quotas_controller.get_account_quotas(**kwargs), 200


@iscsi.route("/quotas", methods=["POST"])
@auth.account_auth_required
def set_account_iscsi_quota(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return quotas_controller.create(**kwargs), 201


@iscsi.route("/quotas/<id>", methods=["PUT"])
@auth.account_auth_required
def update_iscsi_quota(*args,**kwargs):
    kwargs["body"] = request_json(request)
    return quotas_controller.update(*args, **kwargs), 200


@iscsi.route("/quotas/<id>", methods=["DELETE"])
@auth.account_auth_required
def destroy_iscsi_quota(*args,**kwargs):
    return quotas_controller.destroy(*args, **kwargs), 204


@iscsi.route("/configs", methods=["POST"])
@auth.account_auth_required
def create_iscsi_config(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return controller.set_iscsi_configs(**kwargs), 201


@iscsi.route("/configs", methods=["GET"])
@auth.account_auth_required
def get_iscsi_configs(*args, **kwargs):
    return controller.get_configs(**kwargs), 200


@iscsi.route("/configs/<config_id>", methods=["GET"])
@auth.account_auth_required
def get_config(*args, **kwargs):
    return controller.get_config(*args, **kwargs), 200


@iscsi.route("/configs/<config_id>", methods=["DELETE"])
@auth.account_auth_required
def delete_config(*args, **kwargs):
    return controller.delete_config(*args, **kwargs), 204


@iscsi.route("/configs/<config_id>/disks/<disk_id>", methods=["DELETE"])
@auth.account_auth_required
def delete_config_disk(*args, **kwargs):
    data = controller.delete_config_disk(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>", methods=["DELETE"])
@auth.account_auth_required
def delete_disk(*args, **kwargs):
    data = controller.delete_disk(*args, **kwargs)
    return process_response(data)


@iscsi.route("/configs/<config_id>/disks/<disk_id>", methods=["PUT"])
@auth.account_auth_required
def update_disk_legacy(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.update_disk_legacy(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>", methods=["PUT"])
@auth.account_auth_required
def update_disk(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.update_disk(*args, **kwargs)
    return process_response(data)

@iscsi.route("/configs/<config_id>/gateways", methods=["GET"])
@auth.account_auth_required
def get_config_gateways(*args, **kwargs):
    data = controller.get_config_gateways(*args, **kwargs)
    return process_response(data)


@iscsi.route("/configs/<config_id>/disks", methods=["GET"])
@auth.account_auth_required
def get_config_disks(*args, **kwargs):
    data = controller.get_config_disks(*args, **kwargs)
    return process_response(data)


@iscsi.route("/configs/<config_id>/disks", methods=["POST"])
@auth.account_auth_required
def create_config_disk(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.create_config_disk(*args, **kwargs)
    return process_response(data)


@iscsi.route("/clients", methods=["POST"])
@auth.account_auth_required
def create_iscsi_client(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return controller.create_iscsi_client(**kwargs), 201


@iscsi.route("/clients", methods=["GET"])
@auth.account_auth_required
def get_iscsi_clients(*args, **kwargs):
    return controller.get_iscsi_clients(**kwargs), 200


@iscsi.route("/clients/<client_id>", methods=["DELETE"])
@auth.account_auth_required
def delete_client(*args, **kwargs):
    return controller.delete_client(*args, **kwargs), 204


@iscsi.route("/clients/<client_id>", methods=["PUT"])
@auth.account_auth_required
def update_client(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return controller.update_client(*args, **kwargs), 200


@iscsi.route("/clients/<client_id>/disks", methods=["POST"])
@auth.account_auth_required
def disks_to_client(*args, **kwargs):
    kwargs["body"] = request_json(request)
    return controller.disks_to_client(*args, **kwargs)


@iscsi.route("/clients/<client_id>/disks/<disk_id>", methods=["DELETE"])
@auth.account_auth_required
def unassign_client_disk(*args, **kwargs):
    return controller.unassign_client_disk(*args, **kwargs)


@iscsi.route("/clients/<client_id>/disks", methods=["GET"])
@auth.account_auth_required
def get_client_disks(*args, **kwargs):
    return controller.get_client_disks(*args, **kwargs)


@iscsi.route("/disks/<disk_id>/snapshots", methods=["GET"])
@auth.account_auth_required
def get_disk_snapshots(*args, **kwargs):
    data = controller.get_disk_snapshots(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>/snapshots", methods=["POST"])
@auth.account_auth_required
def create_disk_snapshot(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.create_disk_snapshot(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>", methods=["GET"])
@auth.account_auth_required
def get_snapshot(*args, **kwargs):
    data = controller.get_snapshot(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>", methods=["PUT"])
@auth.account_auth_required
def update_snapshot(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.update_snapshot(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>", methods=["DELETE"])
@auth.account_auth_required
def delete_snapshot(*args, **kwargs):
    data = controller.delete_snapshot(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>/new_disk", methods=["POST"])
@auth.account_auth_required
def new_disk_from_snapshot(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.new_disk_from_snapshot(*args, **kwargs)
    return process_response(data)


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>/rollback", methods=["POST"])
@auth.account_auth_required
def rollback_snapshot(*args, **kwargs):
    kwargs["body"] = request_json(request)
    data = controller.rollback_snapshot(*args, **kwargs)
    return process_response(data)
