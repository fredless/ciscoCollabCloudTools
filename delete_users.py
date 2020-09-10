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
Lists and mass deletes users in a Control Hub org.  DANGER!
"""

import itertools
import os
import shutil

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

# specify users to NOT delete by base64 userid or email address
SKIP_USERS = ({
    'id': (
    ),
    'email': (
    )
    })

# to specify an explicit list of users to delete *instead*, provide a list here
SPECIFIC_USERS = (
    'someuser@org.com'
)


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

def user_attribs(user):
    """repeatable user object parsing"""
    return ({'id': user.id,
             'name': user.displayName,
             'created':user.created,
             'modified':user.lastModified,
             'email':user.emails[0]})

def main():
    """finds all in an org and lets you select which to delete"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']
    wxteams_org = wxteams_config['org']

    # https://github.com/CiscoDevNet/webexteamssdk/ abstracts most of the work
    api = WebexTeamsAPI(access_token=wxteams_token)

    user_list = list()
    delete_list = list()

    count = 1
    if SPECIFIC_USERS:
        # Query a the provided list of users
        print_status('Querying user list, please wait...')

        for email in SPECIFIC_USERS:
            for user in api.people.list(email=email):
                print_status(f'Grabbing user #{count} of {len(SPECIFIC_USERS)}: {user.displayName}')
                user_list.append(user_attribs(user))
            count += 1

    else:
        # Query a list of all users
        print_status('Querying org list, please wait...')

        for user in api.people.list(max=PAGE_SIZE, orgId=wxteams_org):
            print_status(f'Grabbing list of users #{count}: {user.displayName}')
            user_list.append(user_attribs(user))
            count += 1


    print_status('Finished querying users.', linefeed=2)
    print(f'Total users: {len(user_list)}\n')

    for user in user_list:
        if user['id'] in SKIP_USERS['id'] or user['email'] in SKIP_USERS['email']:
            print(f'Skipping: {user["name"]}')
        else:
            delete_list.append({'id': user['id'], 'name': user['name']})

    print(f'\nTotal deletions to process: {len(delete_list)}\n')

    if not input("#DANGER# Continue? (y/n): ").lower().strip()[:1] == "y":
        exit()

    print('Continued!')
    count = 1
    for user in delete_list:
        print_status(f'Deleting users #{count}: {user["name"]}')
        api.people.delete(personId=user['id'])

        count += 1



if __name__ == "__main__":
    main()
