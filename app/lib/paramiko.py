"""
Paramiko module
"""

import json

import paramiko

from app import consts
from app.lib.request_utils import abort, log, ok


def send(command):
    """
    Send a bash command to a remote host via Paramiko SSHClient.
    """
    try:
        # Log the request information
        log.info("======================================")
        log.info(f"Request to {consts.CEPH_SSH_HOST} via Paramiko command: {command}")
        log.info("======================================")

        # Create an SSH client object and set the missing host key policy
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the remote host using SSH
        client.connect(
            hostname=consts.CEPH_SSH_HOST,
            port=consts.CEPH_SSH_PORT,
            username=consts.CEPH_SSH_USER,
            key_filename=consts.CEPH_SSH_KEY,
        )

        # Execute the command on the remote host and get the response
        stdin, stdout, stderr = client.exec_command(command)
        response = stdout.read().decode("utf-8")

        # Log the response information
        log.debug("======================================")
        log.debug(f"{stderr.read()}")
        log.debug(f"{response}")
        log.debug(f"{len(response)}")
        log.debug(f"{type(response)}")
        log.debug(f"{json.loads(response)}")
        log.debug("======================================")

        # Parse the response as JSON
        response = json.loads(response)

        # Log the debug information
        log.debug(f"Response from {consts.CEPH_SSH_HOST}: {response}")

        # Return the response as a successful result
        return ok(response)

    # Handle the exception when the Ceph host is unreachable
    except paramiko.ssh_exception.NoValidConnectionsError: # pylint: disable=no-member
        return abort("Ceph host is unreachable")
