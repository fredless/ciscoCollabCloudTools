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
Scans the group spaces you belong to and reports any locked spaces that have only a
single moderator, highlighting spaces at risk of being left without an active moderator.
"""

import os
import sys

import yaml
from webexpythonsdk import WebexAPI, ApiError

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

def main():
    """checks user's space list for single moderator spaces"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    api = WebexAPI(access_token=wxteams_token)

    # validate the auth token up front (raises ApiError on a bad or expired token)
    try:
        api.people.me()
    except ApiError as error:
        print(error)
        if error.status_code == 401:
            print('### Please check that a fresh auth token has been specified in config file. ###')
        sys.exit()

    print('Building space list, please wait...')


    # Populate list of query matches from full list, case insensitive
    space_matchlist = list()
    space_fulllist = list(api.rooms.list(type='group', sortBy='lastactivity'))

    total_spaces = len(list(space_fulllist))
    current_space = 1

    for space in space_fulllist:
        print(f'Working on {current_space} of {total_spaces}: {space.title}... ')
        moderators = []
        if space.isLocked:
            print('locked')
            memberships = api.memberships.list(roomId=space.id)
            for membership in memberships:
                if membership.isModerator:
                    moderator = api.people.get(personId=membership.personId)
                    moderators.append(moderator.displayName)
            if len(moderators) == 1:
                space_matchlist.append([space.title, moderators[0]])
        else:
            print('unlocked')
        current_space += 1

    print(space_matchlist)

if __name__ == "__main__":
    main()
