# Copyright (C) 2020 Frederick W. Nielsen
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
Looks up a Webex user by email and lists every space (room) they are a member of, with each
space's title, type, and room ID, output as CSV.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import re
import sys

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

def get_user(email, api):
    """return Webex user(s) matching an email"""
    return list(api.people.list(email=email))

def room_info(room_id, api):
    """return a room's (title, type), or placeholders if it can't be retrieved"""
    try:
        room = api.rooms.get(room_id)
        return room.title, room.type
    except ApiError:
        return '(unable to retrieve title)', ''

def main():
    """list every space a given user belongs to"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    # validate the auth token up front (raises ApiError on a bad or expired token)
    try:
        api.people.me()
    except ApiError as error:
        print(error)
        if error.status_code == 401:
            print('### Please check that a fresh auth token has been specified in config file. ###')
        sys.exit()

    if len(sys.argv) == 1:
        user_email = input('Please enter the email address of the target user: ')
    else:
        user_email = str(sys.argv[1])

    if not valid_smtp(user_email):
        return

    users = get_user(user_email, api)
    if not users:
        print('### no matching users found with that email address ###')
        return

    user = users[0]

    memberships = list(api.memberships.list(personId=user.id))
    if not memberships:
        print(f'{user_email} is not a member of any spaces.')
        return

    print(f'\n{user_email} is a member of {len(memberships)} space(s):\n')
    print('"title","type","roomId"')
    for membership in memberships:
        title, room_type = room_info(membership.roomId, api)
        print(f'"{title}","{room_type}","{membership.roomId}"')

if __name__ == "__main__":
    main()
