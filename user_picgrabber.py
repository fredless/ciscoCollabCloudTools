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
Looks up a Webex user by email and downloads their profile picture (avatar) to a PNG file
named after their email address.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import re
import sys

import requests
import yaml
from webexpythonsdk import WebexAPI

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

def get_user(email, api):
    """return Teams user by email"""
    return list(api.people.list(email=email))

def main():
    """main thread"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)
    if len(sys.argv) == 1:
        user_email = input('Please enter name the email address of the target user: ')
    else:
        user_email = str(sys.argv[1])

    if not valid_smtp(user_email):
        return False

    users = get_user(user_email, api)
    if not users:
        print('### no matching users found with that email address ###')
        return False
    else:
        user = users[0].to_dict()

    if 'avatar' not in user:
        print(f'### {user_email} has no avatar set ###')
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
