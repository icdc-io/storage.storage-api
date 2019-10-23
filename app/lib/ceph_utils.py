"""
Ceph utils module
"""

import boto3
from botocore.client import Config
from rgwadmin import RGWAdmin

import app.consts as consts


def ceph_connection(
    access_key=consts.CEPH_ACCESS_KEY, secret_key=consts.CEPH_SECRET_KEY
):
    """
    RGW Admin connector
    """
    return RGWAdmin(
        access_key=access_key,
        secret_key=secret_key,
        server=f"{consts.CEPH_HOST}:{consts.CEPH_PORT}",
        secure=False,
        verify=False,
    )


'''
def boto_conn(access_key=consts.CEPH_ACCESS_KEY, secret_key=consts.CEPH_SECRET_KEY):
    """
    boto connector (for creatig buckets with different types on storage)
    """
    return boto.connect_s3(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        host=consts.CEPH_HOST,
        port=int(consts.CEPH_PORT),
        calling_format=boto.s3.connection.OrdinaryCallingFormat(),
        is_secure=False,
    )
'''


def boto3_conn(access_key=consts.CEPH_ACCESS_KEY, secret_key=consts.CEPH_SECRET_KEY):
    """
    boto3 connector (for creating buckets with different types of storage)
    """
    # Create a boto3 session
    session = boto3.Session(
        aws_access_key_id=access_key, aws_secret_access_key=secret_key
    )

    # Use the session to create a client for S3 service, specifying host and port
    s3_client = session.client(
        "s3",
        endpoint_url=f"http://{consts.CEPH_HOST}:{consts.CEPH_PORT}",
        use_ssl=False,
        config=Config(signature_version="s3v4"),
    )

    return s3_client
