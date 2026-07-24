# Copyright (C) 2026 Frederick W. Nielsen
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
Adds a single user (by email) to a Webex space (room) as a regular member. Both the email and
the space are supplied as command-line arguments, making it easy to drive in bulk -- e.g. a
batch file looping over a spreadsheet of users to add them all to one space.

Usage: addusertoSpace.py <user_email> <space_id>
  <space_id> is the base64 room identifier from Control Hub / the Webex API.

The tool assumes your token is entitled to add members to the space. That is not always true --
a space may be moderated by someone else, in which case only its moderators can add members and
the API returns 403 Forbidden. That case (and any other API failure) is reported clearly rather
than dumped as a traceback. Exits non-zero on bad input or an API failure so callers can detect
per-user errors.

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

USAGE = 'Usage: addusertoSpace.py <user_email> <space_id>'

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###')
        return False
    return True

def main():
    """add a user to a space, with the email and space id supplied as command-line arguments"""
    # Windows consoles/pipes default to cp1252, which can't encode emoji or other non-Latin-1
    # characters in Webex-supplied text (space titles, display names) -- force UTF-8 so output
    # never dies with a UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    if len(sys.argv) != 3:
        print(USAGE)
        sys.exit(1)

    user_email = sys.argv[1]
    space_id = sys.argv[2]

    if not valid_smtp(user_email):
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.safe_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    try:
        api.memberships.create(roomId=space_id, personEmail=user_email, isModerator=False)
        print(f'Added {user_email} to space {space_id}')
    except ApiError as error:
        # a moderated space rejects non-moderators with 403; call that out specifically so it is
        # not mistaken for a bad token, then fall through to exit non-zero like any other failure
        if error.status_code == 403:
            print(f'### Not permitted to add {user_email} to space {space_id}: the space is '
                  'likely moderated by someone else, so only its moderators can add members. ###')
        else:
            print(f'### Failed to add {user_email}: {error} ###')
        sys.exit(1)

if __name__ == "__main__":
    main()
