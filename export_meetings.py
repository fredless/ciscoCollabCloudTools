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
from time import sleep

import requests
import yaml

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

BASE_URL = 'https://webexapis.com/v1/meetings'
PAGE = 100
DEFAULT_DAYS = 182

CSV_HEADER = ['start', 'end', 'recurrence', 'title', 'meetingNumber', 'host', 'hostEmail']

def api_get(session, url, params):
    """GET against the API, retrying on rate limiting; exits on any other error"""
    while True:
        response = session.get(url, params=params)
        if response.status_code in (200, 201):
            return response.json()
        if response.status_code == 429:
            print('server busy, retrying...', file=sys.stderr)
            sleep(1)
            continue
        print(f'API call encountered error:\n{response.status_code}: '
              f'{response.content.decode("utf-8")}', file=sys.stderr)
        raise SystemExit(1)

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
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

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

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {wxteams_token}"})

    writer = csv.writer(sys.stdout)
    writer.writerow(CSV_HEADER)

    for user in users:
        print(f'Retrieving meetings for {user}...', file=sys.stderr)
        params = {'max': PAGE,
                  'hostEmail': user,
                  'from': date_from.isoformat(timespec='seconds'),
                  'to': date_to.isoformat(timespec='seconds'),
                  'siteUrl': site_url}
        meeting_list = api_get(session, BASE_URL, params)

        for meeting in meeting_list.get('items', []):
            writer.writerow([
                meeting.get('start', ''),
                meeting.get('end', ''),
                meeting.get('recurrence', ''),
                meeting.get('title', ''),
                meeting.get('meetingNumber', ''),
                meeting.get('hostDisplayName', ''),
                user,
            ])

if __name__ == "__main__":
    main()
