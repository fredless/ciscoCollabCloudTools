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
Lists every license type in a Control Hub org along with the users assigned to each.
"""

import itertools
import os
import shutil

import yaml
from webexpythonsdk import WebexAPI

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

SPINNER = itertools.cycle(['-', '/', '|', '\\'])
PAGE_SIZE = 500

def print_status(text, linefeed=0):
    """output status line"""
    text = f'{next(SPINNER)} {text}'
    screen_width = shutil.get_terminal_size((80, 0))[0]
    print(text +
          ' ' * (screen_width-(len(text)+1)) +
          '\b' * (screen_width -1) +
          '\n' * linefeed,
          end='')

def main():
    """lists all licenses in the org and the users assigned to each"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']
    # optional: query a specific org by id, only applied when set in config.yml
    org_id = wxteams_config.get('org_id')

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    # orgId is only passed when an org_id is present in config.yml
    org_query = {'orgId': org_id} if org_id else {}

    # Build a map of every license in the org and an empty user bucket per license.
    licenses, license_users = dict(), dict()

    print_status('Querying license list, please wait...')
    for wx_license in api.licenses.list(**org_query):
        licenses[wx_license.id] = wx_license
        license_users[wx_license.id] = list()

    # Query a list of all users and bucket them under each license they hold.
    for user in api.people.list(max=PAGE_SIZE, **org_query):
        print_status(f'Grabbing list of users: {user.displayName}')
        if user.licenses:
            for license_id in user.licenses:
                # users can carry licenses from other orgs; skip any we did not enumerate
                if license_id in license_users:
                    license_users[license_id].append({'name': user.displayName, 'email': user.emails[0]})

    print_status('Finished querying users.', linefeed=2)

    for license_id, users in sorted(license_users.items(), key=lambda item: licenses[item[0]].name):
        wx_license = licenses[license_id]
        print(f'**{wx_license.name}** ({wx_license.consumedUnits}/{wx_license.totalUnits} units assigned)')
        for user in users:
            print(f'* {user["name"]} ({user["email"]})')
        print()

if __name__ == "__main__":
    main()
