from typing import List

import json


def info_from_bearerAuth(token):
    """
    Check and retrieve authentication information from custom bearer token.
    Returned value will be passed in 'token_info' parameter of your operation function, if there is one.
    'sub' or 'uid' will be set in 'user' parameter of your operation function, if there is one.

    :param token Token provided by Authorization header
    :type token: str
    :return: Decoded token information or None if token is invalid
    :rtype: dict | None
    """
  
    """
    Until we get real token we assume that we get a unencrypted json in format
    {
        "sub": "asharapov@ibagrou.eu", 
        "accounts": [
            {
                "account":"2dep",
                "role":"admin"
            },
            {
                "account":"ibaby",
                "role":"member"
            }
            ...
        ]
    } 
    """


    return json.loads(token)


