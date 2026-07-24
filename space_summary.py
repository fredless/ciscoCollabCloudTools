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
Summarizes one or more Webex spaces (rooms), given their base64 room ids, as CSV: title, owning
team name, whether the space is moderated (locked), member count, last activity timestamp, and
the room id itself (handy for correlating rows back to a large input list). Handy for a quick
spreadsheet of spaces you have the id for. The team column is blank for a standalone space, holds the team name for a
team-backed space, and shows "(not a member)" when the space belongs to a team you cannot read
(e.g. you are not a member of it).

Usage: space_summary.py [-n|--no-members] [--stdin] <space_id> [<space_id> ...]
  <space_id>         a base64 room identifier from Control Hub / the Webex API.
  --stdin (or -)     also read space ids from stdin, one per line (blank lines ignored).
  -n / --no-members  skip the member count.

Space ids can be given as arguments, piped in via --stdin, or both -- use --stdin for hundreds
of ids, since a long argument list is awkward and hits command-line length limits. For example:
  Get-Content ids.txt | python space_summary.py --stdin
  python user_sharedspaces.py someone@example.com | ... | python space_summary.py --stdin

The title and last-activity come from a single fast room lookup. The member count, however,
requires listing every membership in the space, which for very large spaces (or many spaces at
once) can be slow -- pass -n / --no-members to skip it and leave that column blank.

CSV is written to stdout; per-space warnings go to stderr, so output can be redirected cleanly.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import sys

import yaml
from webexpythonsdk import WebexAPI, ApiError

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

USAGE = 'Usage: space_summary.py [-n|--no-members] [--stdin] <space_id> [<space_id> ...]'

def warn(message):
    """emit a warning to stderr so it never pollutes the CSV on stdout"""
    print(message, file=sys.stderr, flush=True)

def member_count(space_id, api):
    """count the members of a space, or a placeholder if the listing can't be retrieved"""
    try:
        return sum(1 for _ in api.memberships.list(roomId=space_id))
    except ApiError as error:
        warn(f'### could not list members of {space_id}: {error} ###')
        return '(unavailable)'

def team_name(team_id, api, cache):
    """resolve a team id to its name; '' if the space has no team, placeholder if unreadable"""
    if not team_id:
        return ''
    if team_id not in cache:
        # a team we can't read (not a member) returns 403/404 -- report that rather than crash
        try:
            cache[team_id] = api.teams.get(team_id).name
        except ApiError:
            cache[team_id] = '(not a member)'
    return cache[team_id]

def main():
    """summarize one or more spaces as CSV: title, member count, last activity"""
    # Windows consoles/pipes default to cp1252, which can't encode emoji or other non-Latin-1
    # characters in Webex-supplied text (space titles, display names) -- force UTF-8 so output
    # never dies with a UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    # pull the optional flags out of the argument list; whatever remains is a list of space ids
    skip_members = False
    read_stdin = False
    space_ids = []
    for arg in sys.argv[1:]:
        if arg in ('-n', '--no-members'):
            skip_members = True
        elif arg in ('--stdin', '-'):
            read_stdin = True
        else:
            space_ids.append(arg)

    # append ids piped in one per line -- the practical way to pass hundreds of them
    if read_stdin:
        space_ids.extend(line.strip() for line in sys.stdin if line.strip())

    if not space_ids:
        print(USAGE)
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.safe_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    team_cache = {}
    print('"title","team","moderated","members","lastActivity","roomId"')
    for space_id in space_ids:
        try:
            room = api.rooms.get(space_id)
        except ApiError as error:
            warn(f'### could not retrieve space {space_id}: {error} ###')
            continue
        team = team_name(room.teamId, api, team_cache)
        # isLocked is Webex's flag for a moderated space; already on the room, no extra call
        moderated = str(bool(room.isLocked)).lower()
        members = '' if skip_members else member_count(space_id, api)
        print(f'"{room.title}","{team}","{moderated}","{members}","{room.lastActivity}","{room.id}"')

if __name__ == "__main__":
    main()
