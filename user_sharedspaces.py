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
Lists every space (room) that you -- the identity behind wxteams.auth_token -- share with one
other user, given that user's email address as a parameter. Both 1:1 direct spaces and group
spaces are reported; the CSV "type" column distinguishes them.

Webex only permits an unscoped per-person membership query for a Compliance Officer, so this tool
takes the everyday-token route instead: it walks every space you belong to and, for each, runs a
room-scoped membership check for the target user. That needs no elevated privilege, but because a
busy account can belong to thousands of spaces it can take several minutes. Progress is written to
stderr; the CSV result is written to stdout, so output can be redirected cleanly.
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

def progress(message):
    """emit a progress/status line to stderr so it never pollutes the CSV on stdout"""
    print(message, file=sys.stderr, flush=True)

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###')
        return False
    return True

def shares_space(room_id, target_id, target_email, api):
    """return True if the target user is a member of the given room (room-scoped query)"""
    # personId is more reliable than email when we could resolve it; fall back to personEmail
    if target_id:
        members = api.memberships.list(roomId=room_id, personId=target_id)
    else:
        members = api.memberships.list(roomId=room_id, personEmail=target_email)
    return bool(list(members))

def main():
    """list every space the token's own identity shares with a given other user"""
    # Windows consoles/pipes default to cp1252, which can't encode emoji or other non-Latin-1
    # characters in Webex-supplied text (space titles, display names) -- force UTF-8 so output
    # never dies with a UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.safe_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    # validate the auth token up front and capture our own identity (raises on a bad/expired token)
    try:
        me = api.people.me()
    except ApiError as error:
        print(error)
        if error.status_code == 401:
            print('### Please check that a fresh auth_token has been specified in config file. ###')
        sys.exit()

    if len(sys.argv) == 1:
        other_email = input('Please enter the email address of the other user: ')
    else:
        other_email = str(sys.argv[1])

    if not valid_smtp(other_email):
        return

    # resolve the target to a personId when possible: it makes each per-room check unambiguous and
    # catches an obvious typo before we commit to a multi-minute scan. External/guest users may not
    # resolve, so we warn and fall back to matching by email rather than aborting.
    matches = list(api.people.list(email=other_email))
    if matches:
        target = matches[0]
        target_id = target.id
        progress(f'# target: {target.displayName} <{other_email}>')
    else:
        target_id = None
        progress(f'### {other_email} not found in the directory; matching by email address. '
                 'If it is mistyped, the scan will simply find nothing. ###')

    progress(f'# scanning every space {me.emails[0]} belongs to -- this can take a while...')

    shared = []
    scanned = 0
    for room in api.rooms.list():
        scanned += 1
        try:
            if shares_space(room.id, target_id, other_email, api):
                shared.append(room)
                progress(f'  match: {room.title}')
        except ApiError as error:
            progress(f'  ### skipped a space ({room.id}): {error} ###')
        if scanned % 100 == 0:
            progress(f'  ...{scanned} spaces scanned, {len(shared)} shared so far')

    progress(f'# done: scanned {scanned} spaces, found {len(shared)} shared with {other_email}')

    if not shared:
        print(f'No spaces shared between {me.emails[0]} and {other_email}.')
        return

    print(f'\n{me.emails[0]} shares {len(shared)} space(s) with {other_email}:\n')
    print('"title","type","roomId"')
    for room in shared:
        print(f'"{room.title}","{room.type}","{room.id}"')

if __name__ == "__main__":
    main()
