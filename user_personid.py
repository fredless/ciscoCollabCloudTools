# Copyright (C) 2026 Frederick W. Nielsen
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
Finds the person ID of a Webex user given their email -- handy for users outside your own org,
whom the People API will not return by email at all (it only resolves email within your org).
With a person ID you can then act on a foreign user directly, e.g. via GET /people/{personId}.

A space membership record exposes each member's person ID, so this looks for an existing 1:1
direct space with the user and reads it from there. If none exists, it offers to create one
(which posts a message to the user) and reads the person ID from that.

The person ID is the only thing written to stdout, so the result can be piped or captured. All
status and prompts -- including the room ID of any 1:1 space this has to create -- go to stderr.

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

# a 1:1 space can only be created by posting a message, so we post this single character
# to bring the space into existence and then delete the message again immediately
PLACEHOLDER_MESSAGE = '.'

# Webex offers no per-person direct-space lookup, so to find an existing 1:1 we scan our
# direct spaces (most-recently-active first) one membership-query at a time. This caps how many
# we check before giving up and creating a 1:1 instead -- creating is idempotent, so an older,
# un-scanned 1:1 is simply reused. Raise this if an existing-but-stale 1:1 isn't being found.
DIRECT_SCAN_LIMIT = 200

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###', file=sys.stderr)
        return False
    return True

def confirmed(question):
    """ask the user to confirm a yes/no question"""
    return input(f'{question} (y/n): ').strip().lower() in ('y', 'yes')

def person_id_from_existing_direct(api, email):
    """find an existing 1:1 space with the user and return their person id, or None

    Webex has no "get the direct space with person X" lookup and rejects an unscoped
    membership query, so we scan the most-recently-active direct spaces (up to
    DIRECT_SCAN_LIMIT) and check each for the user.
    """
    target = email.lower()
    for count, room in enumerate(
            api.rooms.list(type='direct', sortBy='lastactivity', max=DIRECT_SCAN_LIMIT), 1):
        try:
            for membership in api.memberships.list(roomId=room.id, personEmail=email):
                if (membership.personEmail or '').lower() == target and membership.personId:
                    return membership.personId
        except ApiError:
            # skip any direct space whose membership we can't read
            continue
        if count >= DIRECT_SCAN_LIMIT:
            break
    return None

def person_id_from_new_direct_space(api, email):
    """create a 1:1 space with the user; return (person_id, room_id), cleaning up the message

    Creating a direct space requires posting a message, so we post a single placeholder
    character and delete it again immediately. The space itself remains (Webex 1:1 spaces
    cannot be removed via the API).
    """
    message = api.messages.create(toPersonEmail=email, text=PLACEHOLDER_MESSAGE)
    room_id = message.roomId

    person_id = None
    for membership in api.memberships.list(roomId=room_id, personEmail=email):
        if membership.personId:
            person_id = membership.personId
            break

    # remove the placeholder message we had to post to bring the space into existence
    try:
        api.messages.delete(message.id)
    except ApiError as error:
        print(f'### Warning: could not delete placeholder message {message.id}: {error}',
              file=sys.stderr)

    return person_id, room_id

def main():
    """find and print the person id for the supplied user email"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    # validate the auth token up front (raises ApiError on a bad or expired token)
    try:
        api.people.me()
    except ApiError as error:
        print(error, file=sys.stderr)
        if error.status_code == 401:
            print('### Please check that a fresh auth token has been specified in config file. ###',
                  file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) == 1:
        user_email = input('Please enter the email address of the target user: ').strip()
    else:
        user_email = sys.argv[1].strip()

    if not valid_smtp(user_email):
        sys.exit(1)

    # first, look for an existing 1:1 space we already have with the user
    room_id = None
    person_id = person_id_from_existing_direct(api, user_email)

    if person_id is None:
        print(f'No 1:1 space with {user_email} found in the {DIRECT_SCAN_LIMIT} most recently '
              'active direct spaces.', file=sys.stderr)
        if not confirmed(f'Create a 1:1 space with {user_email} to look up their person id? '
                         '(this posts a message to them)'):
            print('### Aborted; no person id retrieved. ###', file=sys.stderr)
            sys.exit(1)
        print(f'Creating direct space with {user_email}...', file=sys.stderr)
        try:
            person_id, room_id = person_id_from_new_direct_space(api, user_email)
        except ApiError as error:
            print(f'### Failed to create direct space / read membership: {error}', file=sys.stderr)
            sys.exit(1)
        print(f'Created 1:1 space {room_id} (placeholder message removed).', file=sys.stderr)

    if not person_id:
        print(f'### Could not determine a person id for {user_email}. ###', file=sys.stderr)
        sys.exit(1)

    # the person id is the only thing on stdout (the result this utility exists to produce), so
    # it can be piped or captured cleanly; any created space's room id is logged to stderr above
    print(person_id)

if __name__ == "__main__":
    main()
