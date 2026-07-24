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
Adds users (by email) to Webex spaces (rooms) as regular members. Bulk in BOTH dimensions: give
any number of emails and any number of space ids, and every email is added to every space.

Inputs are supplied as free-form tokens -- as command-line arguments, piped via --stdin (one per
line), or both. Each token is sorted automatically: a token containing "@" is treated as an email
address, everything else as a base64 space id (Control Hub / Webex room identifiers never contain
an "@"). This makes every bulk shape natural, e.g.:
  addusertoSpace.py alice@x.com bob@x.com <space_id_1> <space_id_2>   # 2 users into 2 spaces
  Get-Content emails.txt | python addusertoSpace.py --stdin <space_id>   # many users, one space
  Get-Content space_ids.txt | python addusertoSpace.py --stdin alice@x.com   # one user, many spaces

Usage: addusertoSpace.py [--stdin] <email|space_id> [<email|space_id> ...]

The tool assumes your token is entitled to add members to each space. That is not always true --
a space may be moderated by someone else, in which case only its moderators can add members and
the API returns 403 Forbidden. Each add is attempted independently; failures (a moderated space,
a bad email, any API error) are reported and the run continues. Exits non-zero if ANY add failed,
so bulk callers can detect problems.

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

USAGE = ('Usage: addusertoSpace.py [--stdin] <email|space_id> [<email|space_id> ...]\n'
         '  Tokens are sorted into emails (contain @) and space ids; every email is added to '
         'every space.\n'
         '  --stdin (or -) also reads tokens from stdin, one per line (blank lines ignored).')

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print(f'### {email} is not a valid address format, skipping ###')
        return False
    return True

def collect_tokens():
    """gather tokens from argv (and stdin if requested); return the raw token list"""
    read_stdin = False
    tokens = []
    for arg in sys.argv[1:]:
        if arg in ('--stdin', '-'):
            read_stdin = True
        else:
            tokens.append(arg)
    if read_stdin:
        tokens.extend(line.strip() for line in sys.stdin if line.strip())
    return tokens

def main():
    """add every supplied user (by email) to every supplied space; inputs via args and/or stdin"""
    # Windows consoles/pipes default to cp1252, which can't encode emoji or other non-Latin-1
    # characters in Webex-supplied text (space titles, display names) -- force UTF-8 so output
    # never dies with a UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    tokens = collect_tokens()
    # a token with "@" is an email; anything else is a base64 space id (ids never contain "@")
    emails = [tok for tok in tokens if '@' in tok]
    space_ids = [tok for tok in tokens if '@' not in tok]

    any_failure = False
    valid_emails = []
    for email in emails:
        if valid_smtp(email):
            valid_emails.append(email)
        else:
            any_failure = True  # valid_smtp already reported the bad address

    if not valid_emails or not space_ids:
        print(USAGE)
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.safe_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work
    api = WebexAPI(access_token=wxteams_token)

    # add every email to every space (cartesian product); attempt each independently
    for space_id in space_ids:
        for email in valid_emails:
            try:
                api.memberships.create(roomId=space_id, personEmail=email, isModerator=False)
                print(f'Added {email} to space {space_id}')
            except ApiError as error:
                any_failure = True
                # a moderated space rejects non-moderators with 403; call that out specifically
                if error.status_code == 403:
                    print(f'### Not permitted to add {email} to space {space_id}: the space is '
                          'likely moderated by someone else, so only its moderators can add '
                          'members. ###')
                else:
                    print(f'### Failed to add {email} to space {space_id}: {error} ###')

    if any_failure:
        sys.exit(1)

if __name__ == "__main__":
    main()
