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
Lists current admin role holders in a Control Hub org.
"""

import itertools
import os
import shutil
import time

import yaml
from webexteamssdk import WebexTeamsAPI

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

# user agent for browser fake operations (lifted from Chrome v74)
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
              ' (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36')

SPINNER = itertools.cycle(['-', '/', '|', '\\'])
PAGE_SIZE = 500
SLEEPER = 3

def print_status(text, linefeed=0):
    """output status line"""
    text = f'{next(SPINNER)} {text}'
    screen_width = shutil.get_terminal_size((80, 0))[0]
    print(text +
          ' ' * (screen_width-(len(text)+1)) +
          '\b' * (screen_width -1) +
          '\n' * linefeed,
          end='')

def print_done():
    """close off hanging status output"""
    print(' done.\n\n')

def main():
    """finds all users who have one or more administrative role assignments"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/CiscoDevNet/webexteamssdk/ abstracts most of the work
    api = WebexTeamsAPI(access_token=wxteams_token)

    # Populate list of query matches from full list, case insensitive
    roles, role_users = dict(), dict()
    user_list = list()

    print_status('Querying org list, please wait...')
    for role in api.roles.list():
        roles[role.id] = role.name
        role_users[role.name] = list()

    # Query a list of all users and build role list as we go.
    count = 1
    for user in api.people.list(max=PAGE_SIZE):
        print_status(f'Grabbing list of users #{count}: {user.displayName}')
        if user.roles:
            for role in user.roles:
                role_users[roles[role]].append({'name': user.displayName, 'email':user.emails[0]})
        count += 1
    total = count - 1

    print_status('Finished querying users.', linefeed=2)

    for role, people in role_users.items():
        print(f'{role}:')
        for person in people:
            print(person['name'], person['email'])
        print()

if __name__ == "__main__":
    main()
