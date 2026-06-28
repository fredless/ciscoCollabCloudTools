# Copyright (C) 2023 Frederick W. Nielsen
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
Adds a single user (by email) to a Webex team as a non-moderator member. Both the email and
the team are supplied as command-line arguments, making it easy to drive in bulk -- e.g. a
batch file looping over a spreadsheet of users to add them all to one team.

Usage: addusertoTeam.py <user_email> <team_id>
  <team_id> is the base64 team identifier from Control Hub / the Webex API.

Exits non-zero on bad input or an API failure so callers can detect per-user errors.

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

USAGE = 'Usage: addusertoTeam.py <user_email> <team_id>'

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###')
        return False
    return True

def main():
    """add a user to a team, with the email and team id supplied as command-line arguments"""
    if len(sys.argv) != 3:
        print(USAGE)
        sys.exit(1)

    user_email = sys.argv[1]
    team_id = sys.argv[2]

    if not valid_smtp(user_email):
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    try:
        api.team_memberships.create(teamId=team_id, personEmail=user_email, isModerator=False)
        print(f'Added {user_email} to team {team_id}')
    except ApiError as error:
        print(f'### Failed to add {user_email}: {error} ###')
        sys.exit(1)

if __name__ == "__main__":
    main()
