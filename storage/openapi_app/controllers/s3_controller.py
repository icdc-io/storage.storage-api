import connexion
import six

from storage.openapi_app.models.account_member_quota_info import AccountMemberQuotaInfo  # noqa: E501
from storage.openapi_app.models.bucket_create_or_update_request import BucketCreateOrUpdateRequest  # noqa: E501
from storage.openapi_app.models.bucket_info import BucketInfo  # noqa: E501
from storage.openapi_app.models.error4xx import Error4xx  # noqa: E501
from storage.openapi_app.models.s3_account_info import S3AccountInfo  # noqa: E501
from storage.openapi_app.models.s3user import S3user  # noqa: E501
from storage.openapi_app.models.s3user_create_or_update_request import S3userCreateOrUpdateRequest  # noqa: E501
from storage.openapi_app import util


def accounts_account_account_member_get(user, token_info, account, account_member):  # noqa: E501
    """Returns information how many and with which quota account member can create s3 users

    Returns information how many and with which quota account member (not admins) can create s3 users and how many s3users has been created already by the specified member # noqa: E501

    :param account: 
    :type account: str
    :param account_member: 
    :type account_member: str

    :rtype: AccountMemberQuotaInfo
    """
    return Error4xx("developer", "is idiot"), 400


def accounts_account_get(user, token_info, account, include_usage=None):  # noqa: E501
    """Get account information

    Returns account quota, information about allocated resources and if include_usage parameter is true then also actual resource usage. Only account admins are authorized to get this information  # noqa: E501

    :param account: account name for which information should be returned, e.g. dep2
    :type account: str
    :param include_usage: Whether or not include actual storage  usage for the account. Default is false, because this is a long operation and we do not always need it
    :type include_usage: bool

    :rtype: S3AccountInfo
    """
    return 'do some magic, user ' + user + " with creds: " + json.dumps(token_info)


def accounts_account_s3users_get(user, token_info, account, account_user=None):  # noqa: E501
    """Get s3 users list for the account

    List of s3 users with the details The calls can be issued either by account admins or by account members. Account admins will see all s3users for the account. Account members will only see s3users, which they own # noqa: E501

    :param account: 
    :type account: str
    :param account_user: Indicates that we only need to return s3 users owned by specified account member. Not sure where we need it at the moment, just in case...
    :type account_user: str

    :rtype: List[S3user]
    """
    return 'do some magic!'


def accounts_account_s3users_put(user, token_info, account, s3user_create_or_update_request):  # noqa: E501
    """Create s3 user in specified account

    Create s3 user in specified account. Only account admins are allowed to do this, unless number of s3users in member quota of the account is not zero # noqa: E501

    :param account: 
    :type account: str
    :param s3user_create_or_update_request: 
    :type s3user_create_or_update_request: dict | bytes

    :rtype: S3user
    """
    if connexion.request.is_json:
        s3user_create_or_update_request = S3userCreateOrUpdateRequest.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def s3users_s3_user_buckets_bucket_name_delete(user, token_info, s3_user, bucket_name):  # noqa: E501
    """Delete a bucket with all the data

    Delete a bucket with all the data. Can be done either by account admin or account member who owns s3user. # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str
    :param bucket_name: 
    :type bucket_name: str

    :rtype: str
    """
    return 'do some magic!'


def s3users_s3_user_buckets_bucket_name_get(user, token_info, s3_user, bucket_name):  # noqa: E501
    """Get buckets details for s3 user

    Get buckets details for s3 user. Can be done either by account admin or account member who own s3user. This operation can also be done via S3 REST api by anyone who knows access and secret keys or swift user id and swift secret key. # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str
    :param bucket_name: 
    :type bucket_name: str

    :rtype: List[BucketInfo]
    """
    return 'do some magic!'


def s3users_s3_user_buckets_bucket_name_put(s3_user, bucket_name, bucket_create_or_update_request):  # noqa: E501
    """Change an existing bucket

    Change an existing bucket. Can be done either by account admin or account member who owns s3user. With this call we can change only bucket quota # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str
    :param bucket_name: 
    :type bucket_name: str
    :param bucket_create_or_update_request: 
    :type bucket_create_or_update_request: dict | bytes

    :rtype: BucketInfo
    """
    if connexion.request.is_json:
        bucket_create_or_update_request = BucketCreateOrUpdateRequest.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def s3users_s3_user_buckets_get(user, token_info, s3_user):  # noqa: E501
    """Get list of buckets for s3 user

    Get list of buckets for s3 user. Can be done either by account admin or account member who own s3user. This operation can also be done via S3 REST api by anyone who knows access and secret keys or swift user id and swift secret key. # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str

    :rtype: List[BucketInfo]
    """
    return 'do some magic!'


def s3users_s3_user_buckets_put(user, token_info, s3_user, bucket_create_or_update_request):  # noqa: E501
    """Create a new bucket

    Create bucket for s3 user. Can be done either by account admin or account member who owns s3user.  Buckets can also be created by S3 api, but in order to control quota such buckets will be created with almost zero quota. So, to use such buckets user at first will have to increase the bucket quota via our UI. # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str
    :param bucket_create_or_update_request: 
    :type bucket_create_or_update_request: dict | bytes

    :rtype: BucketInfo
    """
    if connexion.request.is_json:
        bucket_create_or_update_request = BucketCreateOrUpdateRequest.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def s3users_s3_user_delete(user, token_info, s3_user):  # noqa: E501
    """Delete s3 user

    Delete s3 user and all the data.  Account admins can delete any s3 user in the account. Account members can only delete s3user, which they own # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str

    :rtype: str
    """
    return 'do some magic!'


def s3users_s3_user_get(user, token_info, s3_user):  # noqa: E501
    """Get s3 user information

    Get s3 user information.  Account admins can get information for any s3 user in the account. Account members can only get information for the s3 users which they own # noqa: E501

    :param s3_user: s3 user name
    :type s3_user: str

    :rtype: S3user
    """
    return 'do some magic!'


def s3users_s3_user_keys_put(s3_user):  # noqa: E501
    """Re-generate s3 user access and secret keys as well as swift key

    Re-generate s3 user access and secret keys as well as swift key. Account admins can do this for any s3 user in the account. Account members can only re-generate keys for s3user which they own # noqa: E501

    :param s3_user: Registered s3 user name
    :type s3_user: str

    :rtype: S3user
    """
    return 'do some magic!'


def s3users_s3_user_put(user, token_info, s3_user, s3user_create_or_update_request):  # noqa: E501
    """Modify s3 user

    Modify s3 user.  Account admins can modify any s3 user in the account. Account members can only modify s3user_description, max_buckets and default_quota_per_bucket properties for s3users which they own # noqa: E501

    :param s3_user: s3user name, which sould be updated
    :type s3_user: str
    :param s3user_create_or_update_request: 
    :type s3user_create_or_update_request: dict | bytes

    :rtype: S3user
    """
    if connexion.request.is_json:
        s3user_create_or_update_request = S3userCreateOrUpdateRequest.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
