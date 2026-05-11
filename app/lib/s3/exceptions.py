"""
Custom exception class to handle errors from RGW, botocore and paramiko
"""


class CephServiceException(Exception):
    def __init__(self, message: str, code: int = 500, details: str = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details

