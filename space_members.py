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
Prompts for a space name, searches for matching spaces, confirms the selection and then
outputs all members of that space in CSV format (display name, email).

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import sys

import yaml
from webexpythonsdk import WebexAPI

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

def bad_choice():
    """print error string and exit"""
    print('### No spaces found or invalid selection made, exiting.')
    sys.exit()

def matchlist_entry(wx_space):
    """returns dict with space matchlist entry"""
    return {'title': wx_space.title,
            'lastActivity': wx_space.lastActivity,
            'id': wx_space.id}

def list_members(wx_space_id, api):
    """query space members and list names and email in CSV format"""
    members = list(api.memberships.list(roomId=wx_space_id))
    print('"Display Name", "Email"')
    for member in members:
        print(f'"{member.personDisplayName}", "{member.personEmail}"')


def main():
    """allows user to select a space and list its members in CSV format"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    wxteams_spacequery = input('Please enter part of name of space to list members of: ')

    # Query the Webex API for its list of spaces, webexpythonsdk abstracts most of the work
    # https://github.com/WebexCommunity/WebexPythonSDK/
    print('Building space list, please wait...')
    api = WebexAPI(access_token=wxteams_token)

    # Populate list of query matches from full list, case insensitive
    wx_space_matchlist = list()
    wx_space_fulllist = api.rooms.list(type='group', sortBy='lastactivity')
    for wx_space in wx_space_fulllist:
        if wxteams_spacequery.upper() in wx_space.title.upper():
            wx_space_matchlist.append(matchlist_entry(wx_space))

    # Finalize space list
    if not wx_space_matchlist:
        bad_choice()

    elif len(wx_space_matchlist) > 1:
        # multiple matches found, present user with choice
        counter = 1
        print()
        for wx_space in wx_space_matchlist:
            print(f'{counter}: {wx_space["title"]}, id: {wx_space["id"]}, last activity: {wx_space["lastActivity"]}')
            counter += 1

        try:
            space_number = int(input('\nPlease enter number of space to query: '))
        except ValueError:
            bad_choice()

        if space_number >= 1 and space_number <= len(wx_space_matchlist):
            space_number -= 1
        else:
            bad_choice()

    else:
        # one match found, use it
        space_number = 0

    # space selected
    if space_number >= 0 and space_number < len(wx_space_matchlist):
        wx_space_matchlist = [wx_space_matchlist[space_number]]

    else:
        bad_choice()

    for wx_space in wx_space_matchlist:
        print(f'# Working on {wx_space["title"]}, {wx_space["id"]}')
        list_members(wx_space['id'], api)
        print('# Complete.')

if __name__ == "__main__":
    main()
