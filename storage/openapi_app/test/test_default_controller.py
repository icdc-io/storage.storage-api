# coding: utf-8

from __future__ import absolute_import
import unittest

from flask import json
from six import BytesIO

from storage.openapi_app.models.bucket_create_or_update_request import BucketCreateOrUpdateRequest  # noqa: E501
from storage.openapi_app.models.bucket_info import BucketInfo  # noqa: E501
from storage.openapi_app.models.error4xx import Error4xx  # noqa: E501
from storage.openapi_app.models.member_create_info import MemberCreateInfo  # noqa: E501
from storage.openapi_app.models.s3_account_info import S3AccountInfo  # noqa: E501
from storage.openapi_app.models.s3user import S3user  # noqa: E501
from storage.openapi_app.models.s3user_create_or_update_request import S3userCreateOrUpdateRequest  # noqa: E501
from storage.openapi_app.test import BaseTestCase


class TestDefaultController(BaseTestCase):
    """DefaultController integration test stubs"""

    def test_account_account_get(self):
        """Test case for account_account_get

        Get account information
        """
        query_string = [('include_usage', True)]
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/account/{account}'.format(account='account_example'),
            method='GET',
            headers=headers,
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_account_account_member_create_info_get(self):
        """Test case for account_account_member_create_info_get

        Returns information how many and with which quot account member can create s3 users
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/account/{account}/member_create_info'.format(account='account_example'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_account_account_s3users_get(self):
        """Test case for account_account_s3users_get

        Get s3 users list for the account
        """
        query_string = [('account_user', 'account_user_example')]
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/account/{account}/s3users'.format(account='account_example'),
            method='GET',
            headers=headers,
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_account_account_s3users_put(self):
        """Test case for account_account_s3users_put

        Create s3 user in specified account
        """
        s3user_create_or_update_request = {}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/account/{account}/s3users'.format(account='account_example'),
            method='PUT',
            headers=headers,
            data=json.dumps(s3user_create_or_update_request),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_buckets_bucket_name_delete(self):
        """Test case for s3users_s3_user_buckets_bucket_name_delete

        Delete a bucket with all the data
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}/buckets/{bucket_name}'.format(s3_user='s3_user_example', bucket_name='bucket_name_example'),
            method='DELETE',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_buckets_bucket_name_get(self):
        """Test case for s3users_s3_user_buckets_bucket_name_get

        Get buckets details for s3 user
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}/buckets/{bucket_name}'.format(s3_user='s3_user_example', bucket_name='bucket_name_example'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_buckets_bucket_name_put(self):
        """Test case for s3users_s3_user_buckets_bucket_name_put

        Change an existing bucket
        """
        bucket_create_or_update_request = {}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}/buckets/{bucket_name}'.format(s3_user='s3_user_example', bucket_name='bucket_name_example'),
            method='PUT',
            headers=headers,
            data=json.dumps(bucket_create_or_update_request),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_buckets_get(self):
        """Test case for s3users_s3_user_buckets_get

        Get list of buckets for s3 user
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}/buckets'.format(s3_user='s3_user_example'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_buckets_put(self):
        """Test case for s3users_s3_user_buckets_put

        Create a new bucket
        """
        bucket_create_or_update_request = {}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}/buckets'.format(s3_user='s3_user_example'),
            method='PUT',
            headers=headers,
            data=json.dumps(bucket_create_or_update_request),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_delete(self):
        """Test case for s3users_s3_user_delete

        Delete s3 user
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}'.format(s3_user='s3_user_example'),
            method='DELETE',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_get(self):
        """Test case for s3users_s3_user_get

        Get s3 user information
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}'.format(s3_user='s3_user_example'),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_keys_put(self):
        """Test case for s3users_s3_user_keys_put

        Re-generate s3 user access and secret keys as well as swift key
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}/keys'.format(s3_user='s3_user_example'),
            method='PUT',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_s3users_s3_user_put(self):
        """Test case for s3users_s3_user_put

        Modify s3 user
        """
        s3user_create_or_update_request = {}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/storage/s3/s3users/{s3_user}'.format(s3_user='s3_user_example'),
            method='PUT',
            headers=headers,
            data=json.dumps(s3user_create_or_update_request),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
