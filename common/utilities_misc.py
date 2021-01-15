# https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-list-of-lists
# This solution is modified from a recipe in Beazley, D. and B. Jones.
#   Recipe 4.14, Python Cookbook 3rd Ed., O'Reilly Media Inc. Sebastopol, CA: 2013.

from collections import Iterable
import yaml
import sys, traceback
from typing import Dict, Optional
from pathlib import Path
import hashlib
from scipy.constants import mile, foot


def flatten(items):
    """Yield items from any nested iterable; see Reference."""
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            for sub_x in flatten(x):
                yield sub_x
        else:
            yield x


# File looks like
# credentials:
#     username: myusername
#     password: mysupergoodpassword
#     app_id:     c9e43f93cdff4ff59a7de17c4219a0f414929b48c0234c818400c1f67da24564
#     app_secret: 0593518c7a044fa58907f3355082f16290662698e5bc497aa48e038bc3e212ec
#
# Note: hex values generated as follows (random each time):
# import uuid
# print('{}{}'.format(uuid.uuid4().hex, uuid.uuid4().hex))
# print('{}{}'.format(uuid.uuid4().hex, uuid.uuid4().hex))
#
# Alternatively:
# import secrets
# secrets.token_hex(32)


def load_credentials(config_file) -> Dict[str, Dict[str, str]]:
    cfg = {}
    try:
        with open(config_file, 'r') as ymlfile:
            cfg = yaml.safe_load(ymlfile)

    except Exception as ee:
        print(ee)
        traceback.print_exc(file=sys.stdout)

    return cfg


def get_credential(config_file: Path, credential_key: str = 'api_key') -> Optional[str]:
    """
    Get a single credential from yaml file. Usual case is 'api_key'
    :param config_file:
    :param credential_key:
    :return:
    """
    config = load_credentials(config_file)
    credential = config.get('credentials', {}).get(credential_key, None) if config else None

    return credential


def compute_hash(txt, length=6):
    # This is just a hash for debugging purposes.
    #    It does not need to be cryptographically secure, just fast and short.
    hash = hashlib.sha1()
    hash.update(txt.encode("ascii", 'ignore'))
    return hash.hexdigest()[:length]


def miles_to_kilometers(dist_miles: float) -> float:
    return dist_miles * (mile / 1000)


def kilometers_to_miles(dist_kilometers: float) -> float:
    # mile is in units of meters/mile
    return 1000 * dist_kilometers / mile


def kilometers_to_miles_r2(dist_kilometers: float) -> float:
    return round(kilometers_to_miles(dist_kilometers), 2)


def meters_to_feet(dist_meters: float) -> float:
    return dist_meters / foot


def meters_to_miles(dist_meters: float):
    return dist_meters * mile
