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
Prompts for a space name and an AD group, compares members, and then asks if you would like to
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

def print_status(text, linefeed=2):
    """output refreshable status line"""
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
    """sync AD and WX Teams space membership"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wx_config = config_params['wxteams']
    wx_token = wx_config['auth_token']

    ldap_config = config_params['ldap']
    ldap_host = ldap_config['server']
    ldap_user = ldap_config['user']
    ldap_password = ldap_config['password']
    ldap_basedn = ldap_config['basedn']
    ldap_basedn_groups = ldap_config['basedn_groups']

    ldap_basedn_len = len(ldap_basedn)

    wx_spacequery = input('Please enter name of the space to examine: ')

    print('\nBuilding Webex Teams space list, please wait...', end='')
    api = WebexTeamsAPI(access_token=wx_token)
    wx_space_fulllist = list(api.rooms.list(type='group'))
    print_done()

    # Populate list of query matches from full list, case insensitive
    wx_space_matchlist = [{'name': wx_space.title, 'id': wx_space.id}
                          for wx_space in wx_space_fulllist
                          if wx_spacequery.upper() in wx_space.title.upper()]

    if not wx_space_matchlist:
        bad_choice()

    # Finalize space list
    elif len(wx_space_matchlist) > 1:
        # multiple matches found, present user with choice
        for count, wx_space in enumerate(wx_space_matchlist, 1):
            print(f'{count}: {wx_space["name"]}')

        try:
            space_number = int(input('\nPlease enter number of space to compare: '))
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
    if space_number >= 0:
        wx_space_match = {'name': wx_space_matchlist[space_number]['name'],
                          'id': wx_space_matchlist[space_number]['id']}

    else:
        bad_choice()

    # Catalogue space members
    if confirmed(f'Webex Teams \"{wx_space_match["name"]}\" space selected, are you sure?'):
        print(f'Gathering details on \"{wx_space_match["name"]}\" space...', end='')
        wx_space_members = list(api.memberships.list(roomId=wx_space_match['id']))
        print_done()
    else:
        bad_choice()

    ad_dl_query = input_with_default('Please enter name of AD DL to compare against: ',
                                     wx_spacequery)

    # Open LDAP connection to Active Directory
    print(f'Connecting to AD...', end='')
    server = ldap3.Server(ldap_host, use_ssl=True)
    connection = ldap3.Connection(server,
                                  user=ldap_user,
                                  password=ldap_password,
                                  authentication=ldap3.NTLM,
                                  auto_bind=True)
    print_done()

    # set up OU search
    query_parameters = {'search_base': ldap_basedn_groups,
                        'search_filter': f'(&({LDAPFILTER_GROUP})(displayName=*{ad_dl_query}*))',
                        'paged_size': LDAP_PAGE_SIZE,
                        'attributes': LDAP_GROUP_ATTRIBUTES}

    print(f'Querying AD groups...', end='')
    connection.search(**query_parameters)
    print_done()

    ad_dl_matchlist = [{'dn': entry.entry_dn, **entry.entry_attributes_as_dict}
                       for entry in connection.entries]

    if not ad_dl_matchlist:
        bad_choice()

    elif len(ad_dl_matchlist) > 1:
        # multiple matches found, present user with choice
        for count, ad_dl in enumerate(ad_dl_matchlist, 1):
            print(f'{count}: {ad_dl["displayName"][0]} ({ad_dl["dn"]})')

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
        query_parameters = {'search_base': ad_dl_match['dn'],
                            'search_filter': f'({LDAPFILTER_GROUP})',
                            'paged_size': LDAP_PAGE_SIZE,
                            'attributes': ['member']}
        print(f'Querying AD group membership...', end='')
        connection.search(**query_parameters)
        print_done()

        for member in connection.entries[0].member.values:
            print_status(f'Gathering details on {member[:(len(member)-ldap_basedn_len-1)]}')
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

        print_status(' done.')
    else:
        bad_choice()

    # Buid list of AD user to add to space
    wx_space_additions = list()
    for ad_user in ad_dl_userlist:
        if not any(wx_user.personEmail.lower() == ad_user["email"] for wx_user in wx_space_members):
            if confirmed(f'AD user \"{ad_user["name"]}\" ({ad_user["created"]}) ' +
                         f'not in \"{wx_space_match["name"]}\" space, add?'):
                wx_space_additions.append(ad_user["email"])

    # Add users selected to space
    if wx_space_additions:
        for addition in wx_space_additions:
            api.memberships.create(wx_space_match['id'], personEmail=addition)
    else:
        print('### No users selected to add to space!')

    print('\n')

    # Notify if space includes users not in AD
    for wx_user in wx_space_members:
        if not any(ad_user['email'] == wx_user.personEmail.lower() for ad_user in ad_dl_userlist):
            print(f'\"{wx_user.personDisplayName}\" not in {ad_dl_match["displayName"]} AD group!')

    print('\nComplete.')

if __name__ == "__main__":
    main()
