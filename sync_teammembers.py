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
Prompts for a team name and an AD group, compares members, and then asks if you would like to
add\\remove delta memberships
"""

import itertools
import os
import shutil

import ldap3
import yaml
from webexteamssdk import WebexTeamsAPI

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

# user agent for browser fake operations (lifted from Chrome v74)
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
              ' (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36')

EMPTY_THRESHOLD = 1

LDAPFILTER_GROUP = 'objectClass=group'

LDAPFILTER_USER = (
    '(&(objectCategory=person)(objectClass=user)'
    '(mail=*)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'
    )

LDAP_PAGE_SIZE = 1000
LDAP_GROUP_ATTRIBUTES = ['displayName']
LDAP_USER_ATTRIBUTES = ['displayName', 'whenCreated', 'mail']

SPINNER = itertools.cycle(['-', '/', '|', '\\'])

def input_with_default(prompt, default):
    """grab input with supplied default"""
    bck = chr(8) * len(default)
    ret = input(prompt + default + bck)
    return ret or default

def bad_choice():
    """print error string and exit"""
    print('### No spaces found or invalid selection made, exiting.')
    exit()

def confirmed(question):
    """ask user to confirm"""
    answer = input(f'{question} (y/n): ').lower().strip()
    while not(answer == 'y' or answer == 'yes' or answer == 'n' or answer == 'no'):
        print('Input yes or no')
        answer = input(f'{question} (y/n):').lower().strip()
    if answer[0] == 'y':
        return True
    else:
        return False

def status(text, linefeed=0):
    """output status line"""
    text = f'{next(SPINNER)} {text}'
    screen_width = shutil.get_terminal_size((80, 0))[0]
    print(text +
          ' ' * (screen_width-(len(text)+1)) +
          '\b' * (screen_width -1) +
          '\n' * linefeed,
          end='')

def main():
    """sync AD and WX Teams team membership"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    ldap_config = config_params['ldap']
    ldap_host = ldap_config['server']
    ldap_user = ldap_config['user']
    ldap_password = ldap_config['password']
    ldap_basedn = ldap_config['basedn']
    ldap_basedn_groups = ldap_config['basedn_groups']

    ldap_basedn_len = len(ldap_basedn)

    wxteams_teamquery = input('Please enter name of the team to examine: ')

    print('\nBuilding Webex Teams team list, please wait...', end='')
    api = WebexTeamsAPI(access_token=wxteams_token)

    # Populate list of query matches from full list, case insensitive
    wx_team_matchlist = list()
    wx_team_userlist = list()
    wx_team_fulllist = list(api.teams.list(type='group'))

    print(' done.\n\n')

    for wx_team in wx_team_fulllist:
        if wxteams_teamquery.upper() in wx_team.name.upper():
            wx_team_matchlist.append({'name': wx_team.name,
                                      'id': wx_team.id})


    # Finalize team list
    if not wx_team_matchlist:
        bad_choice()

    elif len(wx_team_matchlist) > 1:
        # multiple matches found, present user with choice
        counter = 1
        print()
        for wx_team in wx_team_matchlist:
            print(f'{counter}: {wx_team["name"]}')
            counter += 1

        try:
            team_number = int(input('\nPlease enter number of team to compare: '))
        except ValueError:
            bad_choice()

        if team_number >= 0 and team_number < len(wx_team_matchlist)+1:
            team_number -= 1
        else:
            bad_choice()

    else:
        # one match found, use it
        team_number = 0

    # team selected
    if team_number >= 0:
        wx_team_match = {'name': wx_team_matchlist[team_number]['name'],
                         'id': wx_team_matchlist[team_number]['id']}

    else:
        bad_choice()

    if confirmed(f'Webex Teams \"{wx_team_match["name"]}\" team selected, are you sure?'):
        print(f'Gathering details on \"{wx_team_match["name"]}\" team...', end='')
        wx_team_members = list(api.team_memberships.list(teamId=wx_team_match['id']))
        for member in wx_team_members:
            created = member.created
            wx_team_userlist.append({'name': member.personDisplayName,
                                     'email': member.personEmail.lower(),
                                     'created': f'{created.year}-{created.month}-{created.day}',
                                     'id': member.id})
        print(' done.\n\n')
    else:
        bad_choice()


    ad_dl_query = input_with_default('Please enter name of AD DL to compare against: ',
                                     wxteams_teamquery)

    # Open LDAP connection to Active Directory
    print(f'Connecting to AD...', end='')
    server = ldap3.Server(ldap_host, use_ssl=True)
    connection = ldap3.Connection(server,
                                  user=ldap_user,
                                  password=ldap_password,
                                  authentication=ldap3.NTLM,
                                  auto_bind=True)
    print(' done.\n\n')

    # set up OU search
    query_parameters = {'search_base': ldap_basedn_groups,
                        'search_filter': f'(&({LDAPFILTER_GROUP})(displayName=*{ad_dl_query}*))',
                        'paged_size': LDAP_PAGE_SIZE,
                        'attributes': LDAP_GROUP_ATTRIBUTES}

    print(f'Querying AD groups...', end='')
    connection.search(**query_parameters)
    print(' done.\n\n')

    ad_dl_matchlist = list()
    for entry in connection.entries:
        ad_dl_matchlist.append({'dn': entry.entry_dn, **entry.entry_attributes_as_dict})

    if not ad_dl_matchlist:
        bad_choice()

    elif len(ad_dl_matchlist) > 1:
        # multiple matches found, present user with choice
        counter = 1
        print()
        for ad_dl in ad_dl_matchlist:
            print(f'{counter}: {ad_dl["displayName"][0]} ({ad_dl["dn"]})')
            counter += 1

        try:
            dl_number = int(input('\nPlease enter number of DL to compare: '))
        except ValueError:
            bad_choice()

        if dl_number >= 0 and dl_number < len(ad_dl_matchlist)+1:
            dl_number -= 1
        else:
            bad_choice()

    else:
        # one match found, use it
        dl_number = 0

    # DL selected
    if dl_number >= 0:
        ad_dl_match = {'dn': ad_dl_matchlist[dl_number]['dn'],
                       'displayName': ad_dl_matchlist[dl_number]['displayName'][0]}
    else:
        bad_choice()

    if confirmed(f'AD group \"{ad_dl_match["displayName"]}\" selected, are you sure?'):
        ad_dl_userlist = list()
        query_parameters = {'search_base': ad_dl_matchlist[0]['dn'],
                            'search_filter': f'({LDAPFILTER_GROUP})',
                            'paged_size': LDAP_PAGE_SIZE,
                            'attributes': ['member']}
        print(f'Querying AD group membership...', end='')
        connection.search(**query_parameters)
        print(' done.\n\n')

        for member in connection.entries[0].member.values:
            status(f'Gathering details on {member[:(len(member)-ldap_basedn_len-1)]}')
            query_parameters = {'search_base': member,
                                'search_filter': LDAPFILTER_USER,
                                'paged_size': LDAP_PAGE_SIZE,
                                'attributes': LDAP_USER_ATTRIBUTES}
            connection.search(**query_parameters)
            if connection.entries:
                attributes = connection.entries[0]
                created = attributes.whenCreated.values[0]
                ad_dl_userlist.append({'name': attributes.displayName.values[0],
                                       'email': attributes.mail.values[0].lower(),
                                       'created': f'{created.year}-{created.month}-{created.day}'})

        status(' done.', linefeed=2)

    else:
        bad_choice()

    # Buid list of AD user to add to team
    wx_team_additions = list()
    for ad_user in ad_dl_userlist:
        if not any(wx_user['email'] == ad_user["email"] for wx_user in wx_team_userlist):
            if confirmed(f'AD user \"{ad_user["name"]}\" ({ad_user["created"]}) ' +
                         f'not in \"{wx_team_match["name"]}\" team, add?'):
                wx_team_additions.append(ad_user["email"])

    # Add users selected to team
    if wx_team_additions:
        for addition in wx_team_additions:
            api.team_memberships.create(wx_team['id'], personEmail=addition)
    else:
        print('### No users selected to add to team!')

    print('\n')

    # Notify if space includes users not in AD
    for wx_user in wx_team_userlist:
        if not any(ad_user['email'] == wx_user["email"] for ad_user in ad_dl_userlist):
            print(f'\"{wx_user["name"]}\" not in {ad_dl_match["displayName"]} AD group!')

    print('\nComplete.')

if __name__ == "__main__":
    main()
