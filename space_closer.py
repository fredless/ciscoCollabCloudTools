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
Prompts for a space name, searches for space, confirms match and then empties space of all
users, effectively "closing" it.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import datetime
import os

import yaml
from webexteamssdk import WebexTeamsAPI, ApiError

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

# user agent for browser fake operations (lifted from Chrome v74)
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
              ' (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36')

STALE_DAYS = 60
EMPTY_THRESHOLD = 1

def bad_choice():
    """print error string and exit"""
    print('### No spaces found or invalid selection made, exiting.')
    exit()

def old_date(datestamp, stale_threshold):
    """Compares datestamp with stale date"""
    if datestamp:
        date = datetime.datetime.strptime(datestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
        if date.date() < stale_threshold:
            return True
    return False

def confirmed(question):
    """ask user to confirm"""
    answer = input(question + "(y/n): ").lower().strip()
    print("")
    while not(answer == "y" or answer == "yes" or \
    answer == "n" or answer == "no"):
        print("Input yes or no")
        answer = input(question + "(y/n):").lower().strip()
        print("")
    if answer[0] == "y":
        return True
    else:
        return False

def timestamp():
    """return formatted date-time string"""
    return datetime.datetime.now().strftime('%b %d_%H:%M:%S')

def matchlist_entry(wx_space):
    """returns dict with space matchlist entry"""
    return {'title': wx_space.title,
            'lastActivity': wx_space.lastActivity,
            'id': wx_space.id,
            'creatorId': wx_space.creatorId}

def close_space(members, myself, api):
    """iterate space members and remove them, and then ourself"""
    for member in members:
        if myself not in member.personId:
            print(f'deleting {member.personDisplayName}...')
            membership_delete(member.id, api)
        else:
            member_myself = member.id
    print('Removing ourselves...')
    membership_delete(member_myself, api)

def leave_space(members, myself, api):
    """iterate space members and remove ourself"""
    for member in members:
        if myself in member.personId:
            print('Removing ourselves...')
            membership_delete(member.id, api)

def membership_delete(membership_id, api):
    """execute delete call, wrapped in error handler because errors happen on the reg here"""
    try:
        api.memberships.delete(membership_id)
    except ApiError as error:
        print(f'#### API error: {error}')

def main():
    """compares list of AD users against various collab services"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    wxteams_spacequery = input('Please enter name of space to close (or \'stale\'): ')

    # Query Webex Teams API for its list of users, webexteamssdk abstracts most of the work
    # https://github.com/CiscoDevNet/webexteamssdk/
    print('Building space list, please wait...')
    api = WebexTeamsAPI(access_token=wxteams_token)

    # Grab our personId, we'll need it later
    wxteams_me = api.people.me().id

    # Populate list of query matches from full list, case insensitive
    wx_space_matchlist = list()
    wx_space_fulllist = list(api.rooms.list(type='group', sortBy='lastactivity'))

    if wxteams_spacequery == 'stale':
        print('Finding stale spaces, this may take quite some time...')
        stale_threshold = datetime.date.today() - datetime.timedelta(days=STALE_DAYS)
        # wx_space_fulllist = api.rooms.list(type='group', sortBy='lastactivity')
        for wx_space in wx_space_fulllist:
            if not wx_space.lastActivity or old_date(str(wx_space.lastActivity), stale_threshold):
                wx_space_messages = list(api.messages.list(roomId=wx_space.id, max=500))
                if len(wx_space_messages) <= EMPTY_THRESHOLD:
                    wx_space_matchlist.append(matchlist_entry(wx_space))
    else:
        # Grab our group spaces
        # wx_space_fulllist = api.rooms.list(type='group', sortBy='lastactivity')
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
            print(f'{counter}: {wx_space["title"]}, last activity: {wx_space["lastActivity"]}')
            counter += 1

        try:
            space_number = int(input('\nPlease enter number of space to close (0 for all): '))
        except ValueError:
            bad_choice()

        if space_number >= 0 and space_number < len(wx_space_matchlist)+1:
            space_number -= 1
        else:
            bad_choice()

    else:
        # one match found, use it
        space_number = 0

    # space selected
    wx_space_remove_all = False
    if space_number >= 0:
        wx_space_matchlist = [{'title': wx_space_matchlist[space_number]['title'],
                               'lastActivity': wx_space_matchlist[space_number]['lastActivity'],
                               'id': wx_space_matchlist[space_number]['id'],
                               'creatorId': wx_space_matchlist[space_number]['creatorId']}]
        wx_space_matchtitle = wx_space_matchlist[0]['title']
    else:
        wx_space_matchtitle = 'ALL'
        wx_space_remove_all = True

    if confirmed(f'{wx_space_matchtitle} selected, are you sure?'):
        for wx_space in wx_space_matchlist:
            print(f'Working on {wx_space["title"]}')
            wx_space_members = api.memberships.list(roomId=wx_space['id'])
            if wx_space_remove_all and wx_space['creatorId'] == wxteams_me:
                print('ALL selected and our space, closing')
                close_space(wx_space_members, wxteams_me, api)
            elif wx_space_remove_all and wx_space['creatorId'] != wxteams_me:
                print('ALL selected and NOT our space, leaving')
                leave_space(wx_space_members, wxteams_me, api)
            elif not wx_space_remove_all:
                close_space(wx_space_members, wxteams_me, api)
            print('Complete.')

    else:
        bad_choice()

if __name__ == "__main__":
    main()
