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
Prompts for an existing user (by email) and allows changes to be made to all API writable fields.
Some places in the APIdocs state changing email is an unsupported operation, but seems to work.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import re

import yaml
from webexteamssdk import WebexTeamsAPI, ApiError

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

CONSUMER_ORG = 'Y2lzY29zcGFyazovL3VzL09SR0FOSVpBVElPTi9jb25zdW1lcg'

# last option (email) is special treated and should always remain at the end
MENU = [['First Name ', 'firstName'],
        ['Last Name  ', 'lastName'],
        ['Full Name  ', 'displayName'],
        ['Email      ', 'email']]

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

def wx_admin(myself, roles):
    """check if user if full administrator"""
    for role in roles:
        if role.name == 'Full Administrator' and role.id in myself.roles:
            return True
    print('### Provided token is not a full administrator ###')
    return False

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###')
        return False
    return True

def get_user(email, api):
    """return Teams user by email"""
    return list(api.people.list(email=email))

def change_menu(user):
    """draw menu and solicit user input"""
    menu_item = 1
    print()
    for item in MENU:
        print(f'{menu_item} - {item[0]}: {user[item[1]]}')
        menu_item += 1
    print(f'\n{menu_item} - COMMIT ALL CHANGES')
    choice = int(input('\nPlease enter option to change or commit: '))
    if choice != menu_item:
        new_value = input('Please enter new value: ')
    else:
        new_value = None
    return [choice-1, new_value]

def main():
    """main thread"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']



    # Query Webex Teams API for its list of users, webexteamssdk abstracts most of the work
    # https://github.com/CiscoDevNet/webexteamssdk/
    api = WebexTeamsAPI(access_token=wxteams_token)
    print('Gathering org and admin information, please wait...')

    # Grab our personId, we'll need it later
    try:
        myself = api.people.me()
    except ApiError as error:
        print(error)
        if error.status_code == 401:
            print('### Please check that a fresh auth token has been specified in config file. ###')
        exit()

    user_email = input('Please enter name the email address of the target user: ')
    
    if not wx_admin(myself, list(api.roles.list())) or not valid_smtp(user_email):
        return False

    users = get_user(user_email, api)
    if not users:
        print('### no matching users found with that email address ###')
        return False
    else:
        user = users[0].to_dict()

    if user['orgId'] == CONSUMER_ORG:
        print('### matches user in consumer\\free org')
        return False
    elif user['orgId'] != myself.orgId:
        print('### matches user in another org')
        return False

    user.update(email=user['emails'][0])

    user_modified = commit_change = False
    while not commit_change:
        menu_selection, new_value = change_menu(user)
        if menu_selection >= 0 and menu_selection < len(MENU)-1:
            user.update({MENU[menu_selection][1]: new_value})
            user_modified = True
        elif menu_selection == len(MENU)-1:
            if valid_smtp(new_value):
                new_email = get_user(new_value, api)
                if not new_email:
                    user.update({MENU[menu_selection][1]: new_value})
                    user_modified = True
                else:
                    if new_email[0].orgId == CONSUMER_ORG:
                        print('### conflicts with user in consumer\\free org ###')
                    elif new_email[0].orgId == myself.orgId:
                        print('### conflicts with user in our org ###')
                    else:
                        print('### conflicts with user in another org ###')
        elif menu_selection == len(MENU):
            commit_change = True
        else:
            print('### Invalid menu selection ###')

    if not user_modified or not confirmed('Are you sure'):
        print('### Operation aborted or nothing changed, exiting.###')
        return False

    # Get ready to commit changes
    print('Updating user, please wait...')
    user.update(emails=[user['email']])
    api.people.update(user['id'],
                      emails=user['emails'], displayName=user.get('displayName'),
                      firstName=user.get('firstName'), lastName=user.get('lastName'),
                      avatar=user.get('avatar'), orgId=user['orgId'],
                      roles=user.get('roles'), licenses=user.get('licenses'))
    print('Finished.')
    return True


if __name__ == "__main__":
    main()
