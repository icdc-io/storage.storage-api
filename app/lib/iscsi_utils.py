"""
Manage iSCSI module
"""

import functools
import json

import rados
import rbd
import requests

from app.lib.request_utils import (
    conflict,
    internal_server_error,
    is_failed,
    log,
    no_content,
    not_found,
    ok,
    HttpMethod as methods,
    status_codes
)
from app.models.iscsi_client import IscsiClients
from app.models.pool import Pools
from app.models.account import Accounts

class Iscsi:
    """
    iSCSI Actions for cloud gateway
    """

    def __init__(
            self,
            gateway=None,
            config=None,
            target_iqn=None,
            port=5000
    ):
        self.gateway = gateway
        self.config = config
        self.target_iqn = config.target_iqn if config else target_iqn
        self.pool_name = self._get_pool_name()
        self.account_name = self._get_account_name()
        self.port = port

    def _get_account_name(self) -> str:
        account = Accounts.get_by("id", self.config.account_id)
        return account.name

    def _get_pool_name(self) -> str:
        pool = Pools.get_by("id", self.config.pool_id)
        return f"{pool.type}-{pool.klass}"

    def get_image_name(self, disk_name) -> str:
        """
        Get name of RBD image.
        """
        return f"{self.pool_name}/{self.account_name}_{disk_name}"

    def get_full_disk_name(self, disk_name):
        """
        Get full name of disk with account prefix.
        """
        return f"{self.account_name}_{disk_name}"

    def send_request(self, method: str, request_path: str, body: dict = None) -> dict:
        """
        Send an HTTP request to the cloud gateway API.

        This method handles basic request construction, authentication,
        and response parsing from the iSCSI cloud gateway.

        Args:
            method (str): HTTP method to use (e.g., "GET", "POST", "PUT", "DELETE").
            request_path (str): API endpoint path (e.g., "disk/disk1").
            body (dict, optional): Data to send in the request body (for POST/PUT).

        Returns:
            dict: Formatted response using status code mapping.

        Raises:
            ValueError: If an unsupported HTTP method is provided.
        """
        if not hasattr(requests, method.lower()):
            raise ValueError(f"Unsupported HTTP method: {method}")

        host = self.gateway.ip_address
        request_url = f"http://{host}:{self.port}/api/{request_path.lstrip('/')}"
        auth = (self.gateway.api_user, self.gateway.api_password)

        log.info(f"Sending {method.upper()} request to {request_url}")

        request_func = getattr(requests, method.lower())
        try:
            response = request_func(
                request_url,
                auth=auth,
                data=body,
                verify=False
            )
        except requests.RequestException as e:
            log.error(f"HTTP request to {request_url} failed: {str(e)}")
            return internal_server_error("Failed to connect to gateway.")

        # Decode response content
        data = response.content
        if isinstance(data, bytes):
            try:
                data = json.loads(data)
                message = data.get("message", data)
            except json.JSONDecodeError:
                message = data.decode("utf-8")
        elif data is None:
            message = "No information."
        else:
            message = data

        log.info(f"Received {response.status_code} from {request_url}")
        log.debug(f"Response content: {message}")

        return status_codes.get(response.status_code)(message)

    def assign_gateway(self) -> dict:
        """
        Ensure that an iSCSI target is created and assigned to a portal.

        Workflow:
        1. Verify whether the iSCSI target already exists.
        2. If it does not exist, create it.
        3. Assign the portal to the target.
        4. If binding fails and the target was newly created, roll back by deleting the target.

        Returns:
            dict: API response of the failing step, or a success message.
        """
        log.info(f"Starting configuration of iSCSI target {self.target_iqn}")

        target_created = False  # Flag indicating if the target was newly created in this method

        # step 1: check the target existing
        if is_failed(self.get_target()):
            # step 2: create the target
            response = self.create_target()
            if is_failed(response):
                return response
            target_created = True

        # step 3: assign the portal to the target
        response = self.assign_portal_to_target()
        if is_failed(response):
            # step 4: rollback on failure
            if target_created:
                self.delete_target()
            return response

        log.info(f"Successfully configured iSCSI target {self.target_iqn} with portal {self.gateway.name}")

        return ok("Target configured successfully")

    def create_target(self) -> dict:
        """
        Create iSCSI target
        """
        request_url = f"/target/{self.target_iqn}"
        log.info(f"Create iSCSI target with target_iqn: {self.target_iqn}")

        response = self.send_request(methods.PUT, request_path=request_url)

        return response

    def delete_target(self) -> dict:
        """
        Delete iSCSI target
        """
        if is_failed(self.get_target()):
            return ok("Target already deleted.")

        request_url = f"/target/{self.target_iqn}"
        log.info(f"Delete iSCSI target with target_iqn: {self.target_iqn}")

        response = self.send_request(methods.DELETE, request_path=request_url)

        return response

    def get_target(self) -> dict:
        """
        Get iSCSI target
        """
        request_url = "/targets"
        log.info(f"Get iSCSI target with target_ian: {self.target_iqn}")

        response = self.send_request(
            method=methods.GET,
            request_path=request_url,
        )
        if is_failed(response):
            return response

        data = response.get('data', {})
        targets = data.get('targets', [])

        if self.target_iqn in targets:
            return ok(self.target_iqn)
        else:
            return not_found("Target with such iqn not found.")

    def assign_portal_to_target(self) -> dict:
        """
        Assign an iSCSI portal on the gateway to the iSCSI target.
        """
        request_url = f"/gateway/{self.target_iqn}/{self.gateway.name}"
        log.info(f"Assign iSCSI portal {self.gateway.name} to target {self.target_iqn}")

        body = {"ip_address": self.gateway.portal_ip_address}
        response = self.send_request(methods.PUT, request_path=request_url, body=body)

        return response

    def unassign_portal_from_target(self) -> dict:
        """
        Unassign an iSCSI portal on the gateway from the target.
        """
        request_url = f"/gateway/{self.target_iqn}/{self.gateway.name}"
        log.info(f"Delet iSCSI portal {self.gateway.name} to {self.target_iqn}")

        response = self.send_request("delete", request_path=request_url)

        return response

    def create_disk(self, body: dict) -> dict:
        """
        Create a new iSCSI disk (Ceph RBD image) and assign it to the target IQN.

        Args:
            body (dict): Parameters for disk creation.
                - name (str): Name of the disk to create.
                - size_gb (int): Size of the disk in gigabytes.
                - create_image (bool, optional): Whether to create the RBD image.
                  If False, assumes the image already exists. Defaults to True.

        Returns:
            dict: API response from the storage backend or an error message.
        """
        image_name = self.get_image_name(body["name"])
        log.info(f"Creating RBD image with name '{image_name}'")

        request_url = f"/disk/{image_name}"

        data = {
            "mode": "create",
            "size": f"{body['size_gb']}g",
            "pool": self.pool_name,
            "create_image": "true" if body.get("create_image", True) else "false",
        }

        response = self.send_request(
            method=methods.PUT,
            request_path=request_url,
            body=data,
        )

        if is_failed(response):
            return response

        response = self._add_disk_to_target_iqn(image_name)

        if is_failed(response):
            self.delete_disk(body["name"])

        return response

    def _add_disk_to_target_iqn(self, image_name: str) -> dict:
        """
        Assign an existing RBD image (disk) to the target IQN.

        Args:
            image_name (str): Name of the RBD image to assign.

        Returns:
            dict: API response indicating success or error.
        """
        log.info(f"Assigning image '{image_name}' to target IQN '{self.target_iqn}'")

        data = {
            "disk": image_name
        }

        request_url = f"targetlun/{self.target_iqn}"

        response = self.send_request(
            method=methods.PUT,
            request_path=request_url,
            body=data,
        )

        return response

    def update_disk(self, disk_name: str, body: dict) -> dict:
        """
        Resize an existing iSCSI disk (Ceph RBD image).

        Args:
            disk_name (str): Name of the disk to update.
            body (dict): Parameters for disk update.
                - size_gb (int): New size of the disk in gigabytes.

        Returns:
            dict: API response from the storage backend or an error message.
        """
        image_name = self.get_image_name(disk_name)
        log.info(f"Resizing RBD image '{image_name}'")

        request_url = f"/disk/{image_name}"

        data = {
            "mode": "resize",
            "size": f"{body['size_gb']}g",
            "pool": self.pool_name,
        }

        response = self.send_request(
            method=methods.PUT,
            request_path=request_url,
            body=data,
        )

        return response

    def delete_disk(self, disk_name: str) -> dict:
        """
        Delete an iSCSI disk (Ceph RBD image) and unassign it from the target IQN.

        Args:
            disk_name (str): Name of the disk to delete.

        Returns:
            dict: API response from the storage backend or an error message.
        """
        image_name = self.get_image_name(disk_name)

        if is_failed(self.get_disk(image_name=image_name)):
            log.info(f"Disk '{image_name}' already deleted.")
            return ok("Disk already deleted.")

        log.info(f"Deleting iSCSI disk '{image_name}'")

        self._unassign_disk_from_target_iqn(image_name)

        request_url = f"/disk/{image_name}"
        data = {"preserve_image": "false"}

        response = self.send_request(
            method=methods.DELETE,
            request_path=request_url,
            body=data,
        )

        return response

    def _unassign_disk_from_target_iqn(self, image_name: str) -> dict:
        """
        Unassign an iSCSI disk (Ceph RBD image) from the target IQN.

        Args:
            image_name (str): Name of the disk (RBD image) to unassign.

        Returns:
            dict: API response indicating success or an error message.
        """
        log.info(f"Unassigning disk '{image_name}' from target IQN '{self.target_iqn}'")

        request_url = f"/targetlun/{self.target_iqn}"
        data = {"disk": image_name}

        response = self.send_request(
            method=methods.DELETE,
            request_path=request_url,
            body=data,
        )

        return response

    def get_disk(self, image_name: str) -> dict:
        """
        Retrieve information about an iSCSI disk (Ceph RBD image).

        Args:
            image_name (str): Either a short disk name (e.g., "disk1"),
                or a full RBD image path including the pool (e.g., "pool1/disk1").

        Returns:
            dict: API response containing disk (image) information or an error message.
        """
        if '/' not in image_name:
            image_name = self.get_image_name(image_name)

        log.info(f"Retrieving RBD image '{image_name}'")

        request_url = f"/disk/{image_name}"

        response = self.send_request(
            method=methods.GET,
            request_path=request_url,
        )

        return response

    def create_client(self, client: IscsiClients) -> dict:
        """
        Create an iSCSI client for the current target and configure CHAP authentication.

        Args:
            client (IscsiClients): Client object containing IQN and CHAP credentials.

        Returns:
            dict: API response indicating success or error.
        """
        if not is_failed(self.get_client(client.iqn)):
            log.info(f"Client with IQN '{client.iqn}' already exists for target '{self.target_iqn}'")
            return ok("Client for this target already created.")

        log.info(f"Creating client with IQN '{client.iqn}' for target '{self.target_iqn}'")

        request_url = f"client/{self.target_iqn}/{client.iqn}"
        response = self.send_request(method=methods.PUT, request_path=request_url)

        if is_failed(response):
            return response

        # Configure CHAP authentication
        request_url = f"/clientauth/{self.target_iqn}/{client.iqn}"
        data = {
            "username": client.chap_username,
            "password": client.chap_password,
        }

        log.info(f"Setting CHAP authentication for client '{client.iqn}' on target '{self.target_iqn}'")

        response = self.send_request(
            method=methods.PUT,
            request_path=request_url,
            body=data,
        )

        if is_failed(response):
            self.delete_client(client)

        return response

    def update_client(self, client: IscsiClients, body: str) -> dict:
        """
        Update CHAP authentication credentials for an existing iSCSI client.

        Args:
            client (IscsiClients): The client object with IQN.
            body (dict): Dictionary containing updated authentication data.
                - chap_username (str): New CHAP username.
                - chap_password (str): New CHAP password.

        Returns:
            dict: API response indicating success or error.
        """
        request_url = f"/clientauth/{self.target_iqn}/{client.iqn}"
        log.info(f"Updating client '{client.iqn}' for target '{self.target_iqn}'")

        data = {
            "username": body["chap_username"],
            "password": body["chap_password"],
        }

        response = self.send_request(
            method=methods.PUT,
            request_path=request_url,
            body=data,
        )

        return response

    def delete_client(self, client: IscsiClients) -> dict:
        """
        Delete an iSCSI client from the target.

        Args:
            client (IscsiClients): The client object to be deleted.

        Returns:
            dict: API response indicating success or an error message.
        """
        if is_failed(self.get_client(client.iqn)):
            log.info(f"Client '{client.iqn}' is already deleted from target '{self.target_iqn}'")
            return ok("Client already deleted.")

        request_url = f"/client/{self.target_iqn}/{client.iqn}"

        log.info(f"Deleting client '{client.iqn}' from target '{self.target_iqn}'")

        response = self.send_request(
            method=methods.DELETE,
            request_path=request_url,
        )

        return response

    def get_client(self, client_iqn: str) -> dict:
        """
        Get iSCSI client.

        Args:
            client_iqn (str): IQN of the client

        Returns:
            Returns:
            dict: API response with client info or error message.
        """
        request_url = f"/_client/{self.target_iqn}/{client_iqn}"
        log.info(f"Get client with iqn {client_iqn} and target iqn {self.target_iqn}")

        response = self.send_request(
            methods.GET, request_path=request_url
        )

        return response

    def assign_disk(self, client: IscsiClients, disk_name: str) -> dict:
        """
        Assign (connect) an iSCSI disk to a client.

        Args:
            client (IscsiClients): The iSCSI client to assign the disk to.
            disk_name (str): Logical name of the disk to assign.

        Returns:
            dict: API response indicating success or an error message.
        """
        log.info(f"Assigning disk '{disk_name}' to client '{client.iqn}'")

        image_name = self.get_image_name(disk_name)

        response = self.create_client(client)
        if is_failed(response):
            return response

        if image_name in self.get_client_disks(client.iqn):
            log.info(f"Disk '{image_name}' is already assigned to client '{client.iqn}'")
            return ok("Disk already assigned.")

        request_url = f"/clientlun/{self.target_iqn}/{client.iqn}"
        data = {"disk": image_name}

        response = self.send_request(
            method=methods.PUT,
            request_path=request_url,
            body=data,
        )

        return response

    def disconnect_disk(self, client_iqn: str, disk_name: str) -> dict:
        """
        Disconnect an iSCSI disk from a client.

        Args:
            client_iqn (str): IQN of the client.
            disk_name (str): Name of the disk.

        Returns:
            dict: API response indicating success or error message.
        """
        image_name = self.get_image_name(disk_name)

        log.info(f"Disconnecting image '{image_name}' from client '{client_iqn}'")
        print("image_name", image_name)
        print("list", self.get_client_disks(client_iqn))
        if is_failed(self.get_disk(image_name)) or image_name not in self.get_client_disks(client_iqn):
            log.info(f"Disk '{image_name}' is already unassigned from client '{client_iqn}'")
            return ok("Disk already unassigned.")

        request_url = f"/clientlun/{self.target_iqn}/{client_iqn}"
        data = {"disk": image_name}

        response = self.send_request(
            method=methods.DELETE,
            request_path=request_url,
            body=data,
        )

        return response

    def get_client_disks(self, client_iqn: str) -> list[str]:
        """
        Retrieve the list of image names assigned to a specific iSCSI client.

        Args:
            client_iqn (str): IQN of the client.

        Returns:
            list[str]: A list of image names assigned to the client.
                       Returns an empty list if the request fails.
        """
        log.info(f"Getting list of disks for client '{client_iqn}'")

        request_url = f"/_clientlun/{self.target_iqn}/{client_iqn}"

        response = self.send_request(
            method=methods.GET,
            request_path=request_url,
        )

        if is_failed(response):
            log.warning(f"Failed to get disks for client '{client_iqn}'")
            return []

        data = response.get("data", {})
        return list(data.keys())

    @staticmethod
    def _ceph_image_decorator(func):
        """
        Decorator that sets up Ceph connection context and provides
        image, rbd instance, and ioctx to the decorated method.

        Injects:
            - ioctx (rados.ioctx): Ceph I/O context.
            - rbd (rbd.RBD): RBD API object.
            - image (rbd.Image): Opened RBD image based on disk name.

        Returns:
            Callable: Wrapped method with Ceph context.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            pool_name = self._get_pool_name()

            disk_name = self.get_full_disk_name(kwargs["disk_name"])

            log.debug(f"Connecting to Ceph pool '{pool_name}' for image '{disk_name}'")

            # Connect to Ceph cluster
            cluster = rados.Rados(conffile="/etc/ceph/ceph.conf", name="client.storage")
            try:
                cluster.connect()
                ioctx = cluster.open_ioctx(pool_name)

                try:
                    rbd_inst = rbd.RBD()
                    try:
                        image = rbd.Image(ioctx, disk_name)
                    except rbd.ImageNotFound:
                        log.error(f"Image '{disk_name}' not found in pool '{pool_name}'.")
                        return not_found("Disk hasn't got the snapshot with such name.")

                    try:
                        # Inject Ceph context into kwargs
                        kwargs.update({
                            "ioctx": ioctx,
                            "rbd": rbd_inst,
                            "image": image,
                        })
                        return func(self, *args, **kwargs)
                    finally:
                        image.close()

                finally:
                    ioctx.close()

            finally:
                cluster.shutdown()

        return wrapper

    @_ceph_image_decorator
    def create_snapshot(self, disk_name: str, **kwargs) -> dict:
        """
        Create a snapshot for the given iSCSI disk.

        Args:
            disk_name (str): Logical name of the disk.
            kwargs: Additional injected context including:
                - body (dict): Request payload containing 'snapshot_name'.
                - image (rbd.Image): Ceph image object.

        Returns:
            dict: API response indicating success or error.
        """
        body = kwargs["body"]
        image_instance = kwargs["image"]

        snapshot_name = body["name"]
        log.info(f"Creating snapshot '{snapshot_name}' for disk '{disk_name}'.")

        try:
            image_instance.create_snap(snapshot_name)
            log.debug(f"Snapshot '{snapshot_name}' successfully created.")
        except rbd.ImageExists:
            log.warning(f"Snapshot '{snapshot_name}' already exists for disk '{disk_name}'.")
            return conflict("Snapshot with such name already exists.")

        snapshot_info = next(
            (s for s in image_instance.list_snaps() if s["name"] == snapshot_name), None
        )

        log.debug(f"Snapshot info: {snapshot_info}")
        return ok(snapshot_info)

    @_ceph_image_decorator
    def update_snapshot(self, disk_name: str, snapshot_name: str, **kwargs) -> dict:
        """
        Rename an existing iSCSI snapshot.

        Args:
            disk_name (str): Name of the disk containing the snapshot.
            snapshot_name (str): Current name of the snapshot.
            kwargs: Additional context injected by the decorator, including:
                - body (dict): Request data containing new snapshot name.
                - image (rbd.Image): Ceph image instance.

        Returns:
            dict: API response indicating success or error.
        """
        body = kwargs["body"]
        image_instance = kwargs["image"]
        new_name = body["name"]

        log.info(
            f"Renaming snapshot from '{snapshot_name}' to '{new_name}' "
            f"on disk '{disk_name}'."
        )

        try:
            image_instance.rename_snap(snapshot_name, new_name)
            log.debug(f"Snapshot '{snapshot_name}' renamed to '{new_name}'.")
        except rbd.ImageNotFound:
            log.error(f"Snapshot '{snapshot_name}' not found on disk '{disk_name}'.")
            return not_found("Disk hasn't got the snapshot with such name.")
        except rbd.ImageExists:
            log.warning(f"Snapshot name '{new_name}' already exists on disk '{disk_name}'.")
            return conflict("New snapshot name already exists.")

        return no_content()

    @_ceph_image_decorator
    def delete_snapshot(self, disk_name: str, snapshot_name: str, **kwargs) -> dict:
        """
        Delete an iSCSI snapshot.

        Args:
            disk_name (str): Name of the disk containing the snapshot.
            snapshot_name (str): Name of the snapshot to delete.
            kwargs: Context injected by the decorator, including:
                - image (rbd.Image): Ceph image instance.

        Returns:
            dict: API response indicating success or error.
        """
        image_instance = kwargs["image"]

        log.info(f"Deleting snapshot '{snapshot_name}' from disk '{disk_name}'.")

        try:
            if image_instance.is_protected_snap(snapshot_name):
                log.debug(f"Snapshot '{snapshot_name}' is protected. Attempting to unprotect.")
                image_instance.unprotect_snap(snapshot_name)
                log.debug(f"Snapshot '{snapshot_name}' successfully unprotected.")

            image_instance.remove_snap(snapshot_name)
            log.debug(f"Snapshot '{snapshot_name}' successfully removed.")

        except rbd.ImageNotFound:
            log.error(f"Snapshot '{snapshot_name}' not found on disk '{disk_name}'.")
            return not_found("Disk hasn't got the snapshot with such name.")

        return no_content()

    @_ceph_image_decorator
    def new_disk_from_snapshot(self, disk_name, snapshot_name, **kwargs):
        """
        Create a new iSCSI disk from an existing snapshot.

        Workflow:
            1. Clone the RBD image from the specified snapshot.
            2. Create a new disk entry in CloudGW without recreating the image.
            3. Flatten the cloned disk to remove its dependency on the snapshot.

        Args:
            disk_name (str): Base name of the disk from which the snapshot was created (before full naming).
            snapshot_name (str): Name of the snapshot to clone from.
            kwargs: Additional context provided by the decorator and information about new disk:
                body (dict): New disk information:
                    name (str): New disk name that will create from snapshot.
                    size_gb(int): Size of the new disk in gigabytes.
                ioctx (rados.ioctx): I/O context for the pool.
                rbd   (rbd.RBD): RBD API object.
                image (rbd.Image): RBD image instance of the source snapshot.

        Returns:
            dict: API response indicating success or failure.
        """
        body = kwargs["body"]
        disk_name = self.get_full_disk_name(disk_name)

        log.info(f"Creating new disk from snapshot: {snapshot_name}, base_disk_name: {disk_name}, new_disk_name: {body['name']}")

        # Step 1: Clone RBD image from snapshot
        response = self._clone_from_snapshot(disk_name, snapshot_name, **kwargs)
        if is_failed(response):
            return response
        log.info(f"Cloned from snapshot '{snapshot_name}' to new disk '{body['name']}'")

        # Step 2: Create disk entry without recreating the image
        response = self.create_disk(body=body | {"create_image": False})
        if is_failed(response):
            return response
        log.info(f"Created disk entry for '{body['name']}', proceeding to flatten")

        # Step 3: Flatten the newly created RBD image
        self._flatten_created_disk(disk_name=body["name"])
        log.info(f"Successfully created and flattened disk '{body['name']}'")

        return ok(response["data"])

    @_ceph_image_decorator
    def _flatten_created_disk(self, disk_name: str, **kwargs) -> None:
        """
        Flatten a cloned RBD image to remove its dependency on the snapshot.

        Args:
            disk_name (str): Full name of the cloned disk image to flatten.
            **kwargs: Context injected by the decorator, containing:
                ioctx (rados.ioctx): I/O context for the pool.
                rbd   (rbd.RBD): RBD API object.
                image (rbd.Image): RBD image instance for the cloned disk.

        Returns:
            None
        """
        log.debug(f"Flattening disk '{disk_name}'")
        kwargs["image"].flatten()
        log.debug(f"Disk '{disk_name}' successfully flattened")

    def _clone_from_snapshot(self, disk_name, snapshot_name, **kwargs):
        """
        Clone a new RBD image from a snapshot.

        Args:
            disk_name (str): Base name of the disk from which the snapshot was created (before full naming).
            snapshot_name (str): Name of the snapshot to clone from.
            kwargs: Additional context provided by the decorator and information about new disk:
                body (dict): New disk information:
                    name (str): New disk name that will create from snapshot.
                    size_gb(int): Size of the new disk in gigabytes.
                ioctx (rados.ioctx): I/O context for the pool.
                rbd   (rbd.RBD): RBD API object.
                image (rbd.Image): RBD image instance of the source snapshot.

        Returns:
            dict: API response indicating success or failure.
        """
        ioctx = kwargs["ioctx"]
        image = kwargs["image"]
        rbd_inst = kwargs["rbd"]
        body = kwargs["body"]

        log.debug(f"Initiating clone from snapshot '{snapshot_name}' for disk '{disk_name}'")

        need_unprotect = False
        if not image.is_protected_snap(snapshot_name):
            log.debug(f"Snapshot '{snapshot_name}' is not protected. Protecting it temporarily.")
            need_unprotect = True
            image.protect_snap(snapshot_name)

        new_disk_name = self.get_full_disk_name(body["name"])
        log.debug(f"New disk will be created as '{new_disk_name}'")

        try:
            rbd_inst.clone(
                ioctx,
                disk_name,
                snapshot_name,
                ioctx,
                new_disk_name,
            )
            log.info(f"Successfully cloned snapshot '{snapshot_name}' to image '{new_disk_name}'")
        except rbd.ImageExists:
            log.warning(f"Image '{new_disk_name}' already exists. Skipping clone.")
            if need_unprotect:
                log.debug(f"Unprotecting snapshot '{snapshot_name}' after failed clone.")
                image.unprotect_snap(snapshot_name)
            return conflict("Disk already exists")

        return no_content()

    @_ceph_image_decorator
    def rollback_snapshot(self, disk_name: str, snapshot_name: str, **kwargs) -> dict:
        """
        Rollback an RBD image to a specified snapshot.

        This operation discards all changes made to the image since the snapshot was taken,
        effectively restoring the image to its previous state. The snapshot must exist.

        Args:
            disk_name (str): Logical name of the iSCSI disk to rollback.
            snapshot_name (str): Name of the snapshot to rollback to.
            **kwargs: Context injected by decorator, includes:
                - image (rbd.Image): Ceph RBD image instance with the snapshot.

        Returns:
            dict: API response with the current image size on success,
                  or error message if the rollback fails.

        Raises:
            rbd.IOError: If the snapshot does not exist or rollback fails due to I/O issues.
        """
        image = kwargs["image"]
        log.info(f"Rolling back disk '{disk_name}' to snapshot '{snapshot_name}'.")

        try:
            image.rollback_to_snap(snapshot_name)
            image_size = image.size()
            log.info(f"Rollback successful. Current size: {image_size} bytes.")
            return ok(image_size)
        except rbd.IOError:
            log.error(f"Failed to rollback disk '{disk_name}' to snapshot '{snapshot_name}'.")
            return internal_server_error("Something went wrong while rolling back the disk.")
