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
Exports scheduled Webex meetings for a set of host users to CSV. Reads a file of host email
addresses, then for each host queries their meetings within a forward date window and prints
one row per meeting (start, end, recurrence, title, meeting number, host).

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone

import yaml
from webexpythonsdk import ApiError, WebexAPI

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

PAGE = 100
DEFAULT_DAYS = 182

CSV_HEADER = ['start', 'end', 'recurrence', 'title', 'meetingNumber', 'host', 'hostEmail']

def read_email_list(path):
    """read a file of host email addresses, one per line"""
    try:
        with open(os.path.expanduser(path), 'r') as handle:
            emails = [line.strip() for line in handle if line.strip()]
    except OSError as error:
        print(f'### Could not read email list file: {error}')
        raise SystemExit(1)
    if not emails:
        print('### Email list file contained no addresses, exiting.')
        raise SystemExit(1)
    return emails

def main():
    """export scheduled meetings for a list of host users to CSV"""
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

    email_file = input('Enter path to a file of host email addresses (one per line): ').strip()
    users = read_email_list(email_file)

    site_url = input('Enter the Webex site URL (e.g. example.webex.com): ').strip()

    days_input = input(f'How many days ahead to include? [{DEFAULT_DAYS}]: ').strip()
    try:
        days = int(days_input) if days_input else DEFAULT_DAYS
    except ValueError:
        print('### Invalid number of days, exiting.')
        raise SystemExit(1)

    date_from = datetime.now(timezone.utc)
    date_to = date_from + timedelta(days=days)

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work,
    # including pagination and rate-limit (429) retries
    api = WebexAPI(access_token=wxteams_token)

    writer = csv.writer(sys.stdout)
    writer.writerow(CSV_HEADER)

    for user in users:
        print(f'Retrieving meetings for {user}...', file=sys.stderr)
        try:
            meetings = api.meetings.list(
                max=PAGE,
                hostEmail=user,
                from_=date_from.isoformat(timespec='seconds'),
                to=date_to.isoformat(timespec='seconds'),
                siteUrl=site_url)
            for meeting in meetings:
                writer.writerow([
                    meeting.start or '',
                    meeting.end or '',
                    meeting.recurrence or '',
                    meeting.title or '',
                    meeting.meetingNumber or '',
                    meeting.hostDisplayName or '',
                    user,
                ])
        except ApiError as error:
            print(f'API call encountered error:\n{error}', file=sys.stderr)
            raise SystemExit(1)

if __name__ == "__main__":
    main()
