"""
Manage iSCSI module
"""

import functools

import rados
import rbd
import requests

from app.lib.controller_utils import status_codes
from app.lib.request_utils import (
    conflict,
    created,
    internal_server_error,
    is_failed,
    log,
    no_content,
    not_found,
    ok,
)
from app.models import account, iscsi_config, iscsi_disk, pool


class Iscsi:
    """
    iSCSI Actions for cloud gateway
    """

    def __init__(
        self,
        protocol=None,
        request=None,
        host=None,
        port=None,
        method=None,
        api_user=None,
        api_password=None,
    ):
        self.protocol = protocol
        self.req = request
        self.host = host
        self.port = port
        self.method = method
        self.api_user = api_user
        self.api_password = api_password

    def send_request(
        self, method, request, auth, host="localhost", port=5000, body=None
    ):
        """
        Request to cloud gateway host
        """
        basic_url = f"http://{host}:{port}/api/"
        request_url = basic_url + request
        log.info(f"Request to {request_url}")
        response = eval(f"requests.{method}")(
            request_url, auth=auth, data=body, verify=False
        )
        log.info(
            f"Response from {request_url} with status code {response.status_code} \
            and content {response.content}"
        )
        return status_codes.get(response.status_code)(response.content)

    def create_disk(self, config, gateway, image, body):
        """
        Create iSCSI disk
        """
        pool_obj = pool.Pools.get_by("id", config.pool_id)
        account_name = account.Accounts.get_by("id", config.account_id).name

        log.info(f"Create iSCSI disk with {account_name}_{body['name']} name")
        log.info(f"Create iSCSI disk with {account_name}_{body['name']} name")

        request_url = (
            f"disk/{pool_obj.type}-{pool_obj.klass}/{account_name}_{body['name']}"
        )

        data = {
            "mode": "create",
            "size": str(body["size_gb"]) + "g",
            "pool": f"{pool_obj.type}-{pool_obj.klass}",
            "create_image": str(image).lower(),
        }

        auth = (gateway.api_user, gateway.api_password)

        response = self.send_request(
            method="put",
            request=request_url,
            auth=auth,
            host=gateway.ip_address,
            body=data,
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

        response = self._add_disk_to_target_iqn(config, gateway, body)
        print(response)
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])  
        return created()

    def update_user(self, client_obj, disk, body):
        """
        Update iSCSI Client
        """
        """
        Update iSCSI Client
        """
        config_obj = iscsi_config.IscsiConfigs.get_by("id", disk.config_id)
        gateway = config_obj.gateways[0]
        auth = (gateway.api_user, gateway.api_password)
        request_url = f"client/{config_obj.target_iqn}/{client_obj.iqn}"
        data = {"username": body["chap_username"], "password": body["chap_password"]}
        request_url = f"clientauth/{config_obj.target_iqn}/{client_obj.iqn}"
        response = self.send_request(
            method="put",
            request=request_url,
            body=data,
            host=gateway.ip_address,
            auth=auth,
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])
        return no_content()

    def delete_iscsi_disk(self, config, gateway, disk_name):
        """
        Deletes rbd image (disk) from ceph, from the specified pool.
        All work is done by sending the following request to iscsi gateway:
        curl -k --user <user>:<password> -d preserve_image=false
        -X DELETE https://172.20.141.36:5000/api/disk/<pool>/diskname
        curl -k --user <user>:<password> -d preserve_image=false
        -X DELETE https://172.20.141.36:5000/api/disk/<pool>/diskname
        """

        pool_obj = pool.Pools.get_by("id", config.pool_id)
        account_name = account.Accounts.get_by("id", config.account_id).name
        request_url = f"targetlun/{config.target_iqn}"
        data = {"disk": f"{pool_obj.type}-{pool_obj.klass}/{account_name}_{disk_name}"}
        auth = (gateway.api_user, gateway.api_password)
        response = self.send_request(
            "delete", request=request_url, body=data, host=gateway.ip_address, auth=auth
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

        request_url = (
            f"disk/{pool_obj.type}-{pool_obj.klass}/{account_name}_{disk_name}"
        )

        data = {"preserve_image": "false"}
        response = self.send_request(
            "delete", request=request_url, body=data, host=gateway.ip_address, auth=auth
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

        return no_content()

<<<<<<< HEAD
=======

>>>>>>> 71b9ae7 (Iscsi)
    def create_iscsi_client(self, config, gateway, client):
        """
        add client: curl -k --user admin:testiscsi -X PUT
        https://172.20.141.36:5000/api/client/iqn.2019-11.io.icdc:ceph-iscsi/iqn.1994-05.com.redhat:myhost4
        """

        """
        add client: curl -k --user admin:testiscsi -X PUT
        https://172.20.141.36:5000/api/client/iqn.2019-11.io.icdc:ceph-iscsi/iqn.1994-05.com.redhat:myhost4
        """

        auth = (gateway.api_user, gateway.api_password)
        request_url = f"client/{config.target_iqn}/{client.iqn}"

        response = self.send_request(
            "put", request=request_url, body=None, host=gateway.ip_address, auth=auth
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

        # CHAP authentication
        request_url = f"clientauth/{config.target_iqn}/{client.iqn}"
        data = {"username": client.chap_username, "password": client.chap_password}
        response = self.send_request(
            "put", request=request_url, body=data, host=gateway.ip_address, auth=auth
        )
        if is_failed(response):
            request_url = f"client/{config.target_iqn}/{client.iqn}"
            self.send_request(
                "delete", request=request_url, host=gateway.ip_address, auth=auth
            )
            return status_codes.get(response["code"])(response["data"])
        return created()

    def assign_disk(self, client_obj, disk_obj, config_obj, gateway_obj):
        """
        Connect iSCSI disk to Client
        """
        self.create_iscsi_client(config_obj, gateway_obj, client_obj)
        request_url = f"clientlun/{config_obj.target_iqn}/{client_obj.iqn}"
        pool_obj = pool.Pools.get_by("id", config_obj.pool_id)
        account_obj = account.Accounts.get_by("id", config_obj.account_id)
        data = {
            "disk": f"{pool_obj.type}-{pool_obj.klass}/{account_obj.name}_{disk_obj.name}"
        }
        auth = (gateway_obj.api_user, gateway_obj.api_password)
        response = self.send_request(
            method="put",
            request=request_url,
            body=data,
            host=gateway_obj.ip_address,
            auth=auth,
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])
        assigned_disks = client_obj.disks
        assigned_disks.append(disk_obj)
        client_obj.save()
        return no_content()

    def disconnect_disk(self, client_obj, disk_obj, config_obj, gateway_obj):
        """
        Disconnect iSCSI disk to Client
        """
        request_url = f"clientlun/{config_obj.target_iqn}/{client_obj.iqn}"
        pool_obj = pool.Pools.get_by("id", config_obj.pool_id)
        account_name = account.Accounts.get_by("id", config_obj.account_id).name
        data = {
            "disk": f"{pool_obj.type}-{pool_obj.klass}/{account_name}_{disk_obj.name}"
        }
        auth = (gateway_obj.api_user, gateway_obj.api_password)
        response = self.send_request(
            method="delete",
            request=request_url,
            body=data,
            host=gateway_obj.ip_address,
            auth=auth,
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])
        disk_obj = iscsi_disk.IscsiDisks.get_by("id", disk_obj.id)
        client_obj.disks.remove(disk_obj)
        client_obj.save()
        return no_content()

    def update_disk(self, disk, config, body):
        """
        Resizes disk in ceph. All work is done by sending the following request to iscsi gateway:
        curl -k --user admin:testiscsi -d mode=resize -d size=5g -d pool=iscsi \
        -X PUT https://172.20.141.36:5000/api/disk/iscsi/disk2
        """
        pool_obj = pool.Pools.get_by("id", config.pool_id)
        account_obj = account.Accounts.get_by("id", config.account_id)
        gateway_obj = config.gateways[0]
        request_url = (
            f"disk/{pool_obj.type}-{pool_obj.klass}/{account_obj.name}_{disk.name}"
        )
        data = {
            "mode": "resize",
            "size": f"{body['size_gb']}g",
            "pool": f"{pool_obj.type}-{pool_obj.klass}",
        }
        auth = (gateway_obj.api_user, gateway_obj.api_password)
        response = self.send_request(
            method="put",
            request=request_url,
            body=data,
            host=gateway_obj.ip_address,
            auth=auth,
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

        return no_content()

    def _add_disk_to_target_iqn(self, config, gateway, body):
        pool_obj = pool.Pools.get_by("id", config.pool_id)
        account_name = account.Accounts.get_by("id", config.account_id).name
        log.info(
            f"Add disk {account_name}_{body['name']} to target iqn {config.target_iqn}"
        )
        auth = (gateway.api_user, gateway.api_password)
        data = {
            "disk": f"{pool_obj.type}-{pool_obj.klass}/{account_name}_{body['name']}"
        }
        request_url = f"targetlun/{config.target_iqn}"
        response = self.send_request(
            method="put",
            request=request_url,
            body=data,
            host=gateway.ip_address,
            auth=auth,
        )
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

        return created()

    def _ceph_image_decorator(func):
        @functools.wraps(func)
        def wrapper(self, **kwargs):
            """
            Wrapper wich connect to ceph and does all the needed things
            before the actual snapshot action is executed
            """
            kwargs = kwargs["body"]
            pool_name, disk = kwargs["pool"], kwargs["disk"]

            # TODO Make used const.py for  name='client.storage'
            cluster = rados.Rados(conffile="/etc/ceph/ceph.conf", name="client.storage")
            try:
                cluster.connect()
                ioctx = cluster.open_ioctx(pool_name)
                try:
                    rbd_inst = rbd.RBD()
                    image = rbd.Image(ioctx, disk)
                    try:
                        kwargs["ioctx"], kwargs["rbd"], kwargs["image"] = (
                            ioctx,
                            rbd_inst,
                            image,
                        )
                        result = func(self, **kwargs)
                    finally:
                        image.close()
                finally:
                    ioctx.close()
            finally:
                cluster.shutdown()

            return result

        return wrapper

    @_ceph_image_decorator
    def create_snapshot(self, **kwargs):
        """
        Create iSCSI Snapshot
        """
        snapshot_name, image_instance = kwargs["name"], kwargs["image"]
        try:
            image_instance.create_snap(snapshot_name)
        except rbd.ImageExists:
            return conflict("Snapshot with such name already exists.")
        return [
            snap
            for snap in list(image_instance.list_snaps())
            if snap["name"] == snapshot_name
        ][0]

    @_ceph_image_decorator
    def update_snapshot(self, **kwargs):
        """
        Update iSCSI Snapshot
        """
        snapshot_name, new_name, image_instance = (
            kwargs["snapshot_name"],
            kwargs["new_snapshot_name"],
            kwargs["image"],
        )
        try:
            image_instance.rename_snap(snapshot_name, new_name)
        except rbd.ImageNotFound:
            return not_found("Disk hasn't got the snapshot with such name.")
        except rbd.ImageExists:
            return conflict("New name of snapshot can't be the same as previous.")
        return no_content()

    @_ceph_image_decorator
    def delete_snapshot(self, **kwargs):
        """
        Delete iSCSI Snapshot
        """
        snapshot_name, image_instance = kwargs["snapshot_name"], kwargs["image"]
        try:
            if image_instance.is_protected_snap(snapshot_name):
                image_instance.unprotect_snap(snapshot_name)
            image_instance.remove_snap(snapshot_name)
        except rbd.ImageNotFound:
            return not_found("Disk hasn't got the snapshot with such name.")
        return no_content()

    @_ceph_image_decorator
    def new_disk_from_snapshot(self, **kwargs):
        """
        Create iSCSI disk based on iSCSI Snapshot
        """
        kwargs["body"] = kwargs
        self._clone_from_snapshot(**kwargs)
        response = self.create_disk(
            config=kwargs["config"],
            gateway=kwargs["gateway"],
            image=False,
            body={
                "size_gb": int(kwargs["snapshot_params"]["size_gb"]),
                "config_id": kwargs["config"].id,
                "name": kwargs["name"],
                "owner": kwargs["owner"],
            },
        )

        kwargs["disk"] = f"{kwargs['account_name']}_{kwargs['name']}"
        params = {}
        params["pool"] = kwargs["pool"]
        params["disk"] = f"{kwargs['account_name']}_{kwargs['name']}"
        params["body"] = kwargs

        self._flatten_created_disk(**params)
        # if is_failed(response):
        # self._delete_cloned_disk(**kwargs)
        return ok(response["data"])
        # self._delete_cloned_disk(**kwargs)

    @_ceph_image_decorator
    def rollback_snapshot(self, **kwargs):
        """
        Rollback snapshot
        """
        try:
            image = kwargs["image"]
            image.rollback_to_snap(kwargs["snapshot_params"]["name"])
            return ok(image.size())
        except rbd.IOError:
            return internal_server_error("Something went wrong while Disk rollback")

    @_ceph_image_decorator
    def _flatten_created_disk(self, **kwargs):
        kwargs["image"].flatten()

    @_ceph_image_decorator
    def _clone_from_snapshot(self, **kwargs):
        """Clones a new disk from a snapshot

        Creates new clone disk  from the snapshot and triggers a background flatten operation
        which  breaks the link betweeen the new disk  and snapshot

        :param pool: ceph pool
        :type pool: str
        :param disk: rbd image in provided pool
        :type disk: str
        :param snapshot_name:
        :type snapshot_name: str
        :param new_disk_name:
        :type new_disk_name: str
        :rtype: RESULT_OK or RESULT_IMAGE_EXISTS or \
        Exception will be raised and caught at upper level
        """

        ioctx, image, rbd, snapshot_name, disk_name, new_disk_name, account_name = (
            kwargs["ioctx"],
            kwargs["image"],
            kwargs["rbd"],
            kwargs["snapshot"],
            kwargs["disk"],
            kwargs["name"],
            kwargs["account_name"],
        )
        need_unprotect = False
        if not image.is_protected_snap(snapshot_name):
            need_unprotect = True
            image.protect_snap(snapshot_name)
        try:
            rbd.clone(
                ioctx,
                disk_name,
                snapshot_name,
                ioctx,
                f"{account_name}_{new_disk_name}",
            )
        except rbd.ImageExists:
            if need_unprotect:
                image.unprotect_snap(snapshot_name)
                return conflict("Disk already exists")
        return no_content

    # # @_ceph_image_decorator
    # def _delete_cloned_disk(self, **kwargs):
    #     """


# Deletes image and removes an entry from the flatten list and attempts to unprotect  snapshot

#     :param pool: ceph pool
#     :type pool: str
#     :param disk: rbd image, which  needs to  be flattened
#     :type disk: str
#     :param ioctx: io context for the pool
#     :type ioctx: rados.Ioctx
#     :param rbd_instance: rbd instance for performing rbd operations
#     :type rbd_instance: rbd.RBD
#     :param image_instance: image instance for performing image operations
#     :type image_instance: rbd.Image

# Deletes image and removes an entry from the flatten list and attempts to unprotect  snapshot

#     ioctx, image, rbd, snapshot_name, disk, new_disk = \
#       kwargs["ioctx"], kwargs["image"], kwargs["rbd"], kwargs["snapshot_name"],\
#       kwargs["disk_name"], kwargs["new_disk_name"]

#     # close the image, since it was opened in decorator
#     # but we do not need image instance for remove operation
#     image.close()
#     rbd.remove(ioctx, disk)


#     try:
#         parent_image = rbd.Image(ioctx, new_disk)
#         try:
#             if parent_image.is_protected_snap(parent_snapshot):
#                 parent_image.unprotect_snap(parent_snapshot)
#         except rbd.ImageBusy:
#             # not an error theoretically  another flatten operation may  be in progress
#             common_utils.log.debug(
#           'Failed to unprotect snapshot %s' % (pool + '/' + parent_disk + '@' + parent_snapshot))
#         finally:
#             parent_image.close()
#     except Exception as ex:
#         # Well, we did all we could. Just log the error  and continue
#         common_utils.log.error(
#             'flatten_image: got exception %s during unprotect' % str(ex))

#     common_utils.log.debug(
#         'delete_cloned_disk(): exiting for %s' % (pool + '/' + disk))
