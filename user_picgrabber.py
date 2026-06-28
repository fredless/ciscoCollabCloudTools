# Copyright (C) 2019 Frederick W. Nielsen
#
# This file is part of Cisco Collaboration Cloud Tools.
#
# Cisco Collaboration Cloud Tools is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# Cisco Collaboration Cloud Tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cisco Collaboration Cloud Tools.  If not, see <http://www.gnu.org/licenses/>.

"""
Looks up a Webex user and downloads their profile picture (avatar) to a PNG file named after
their email address.

Usage: user_picgrabber.py <user_email | person_id>
  The argument is auto-detected: a value containing "@" is looked up by email (same org only);
  anything else is treated as a Webex person ID and fetched directly, which works for users
  outside your own org. Use user_personid.py to obtain a foreign user's person ID.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import re
import sys

import requests
import yaml
from webexpythonsdk import WebexAPI, ApiError

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###')
        return False
    return True

def resolve_user(identifier, api):
    """resolve a Webex person from an email (same-org lookup) or a person ID (works cross-org)

    Returns a Person object, or None if not found / not resolvable.
    """
    if '@' in identifier:
        if not valid_smtp(identifier):
            return None
        matches = list(api.people.list(email=identifier))
        return matches[0] if matches else None
    # not an email -- treat as a person ID and fetch directly (works for foreign-org users)
    try:
        return api.people.get(identifier)
    except ApiError as error:
        print(f'### Could not retrieve person by ID: {error} ###')
        return None

def main():
    """main thread"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    if len(sys.argv) >= 2:
        identifier = sys.argv[1].strip()
    else:
        identifier = input("Enter the target user's email (same org) or person ID: ").strip()

    person = resolve_user(identifier, api)
    if person is None:
        print('### no matching user found ###')
        return

    user = person.to_dict()
    if not user.get('avatar'):
        print(f'### {user.get("emails", [identifier])[0]} has no avatar set ###')
        return

    filename = user['emails'][0].lower() + '.png'
    response = requests.get(user['avatar'], stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f'Saved avatar to {filename}')
    else:
        print(f'### failed to download avatar: HTTP {response.status_code} ###')

if __name__ == "__main__":
    main()
