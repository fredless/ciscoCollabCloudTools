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
Mass-downloads all recordings and transcripts for one or more host users. Requires admin
scope to access recordings other than your own.
"""

import itertools
import os
import re
import shutil

import requests
import yaml

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

SPINNER = itertools.cycle(['-', '/', '|', '\\'])

BASE_URL = 'https://webexapis.com/v1/recordings'

# download link keys returned by the API and the extension to save each download as
LINK_TYPES = [{'key': 'recordingDownloadLink', 'ext': 'mp4'},
              {'key': 'transcriptDownloadLink', 'ext': 'vtt'}]

PAGE = 100

def print_status(text, linefeed=0):
    """output status line"""
    text = f'{next(SPINNER)} {text}'
    screen_width = shutil.get_terminal_size((80, 0))[0]
    print(text +
          ' ' * (screen_width-(len(text)+1)) +
          '\b' * (screen_width -1) +
          '\n' * linefeed,
          end='')

def unique_filename(name, used):
    """return a name unique within this run, appending a counter on collision"""
    root, ext = os.path.splitext(name)
    candidate = name
    counter = 2
    while candidate in used:
        candidate = f'{root} ({counter}){ext}'
        counter += 1
    used.add(candidate)
    return candidate

def main():
    """downloads all recordings and transcripts for the supplied host users"""
    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.full_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    users_input = input('Enter host email(s) to download recordings for (comma-separated): ')
    users = [email.strip() for email in users_input.split(',') if email.strip()]
    if not users:
        print('### No host emails provided, exiting.')
        exit()

    web_client = requests.Session()
    web_client.headers.update({"Authorization": f"Bearer {wxteams_token}"})

    # track names already written so same-topic recordings don't overwrite each other
    used_names = set()

    for user in users:
        print(f'Retrieving recording list for {user}...')
        recording_list = web_client.get(f'{BASE_URL}?max={PAGE}&hostEmail={user}')

        if recording_list.status_code != 200:
            print(f'{recording_list.status_code}: {recording_list.content}')
            continue

        items = recording_list.json()['items']
        if not items:
            print(f'{user} has no recordings.\n')
            continue

        print(f'{user} has {len(items)} recording(s)...')
        for count, summary in enumerate(items, 1):
            print_status(f'Downloading recording {count} of {len(items)}...')
            details = web_client.get(f'{BASE_URL}/{summary["id"]}').json()
            links = details['temporaryDirectDownloadLinks']

            # name files after the recording topic, sanitized for the filesystem
            topic = details.get('topic') or summary['id']
            safe_topic = re.sub(r'[^\w\-. ]', '_', topic).strip() or summary['id']

            for link_type in LINK_TYPES:
                link = links.get(link_type['key'])
                if not link:
                    # e.g. a recording with no transcript available
                    continue
                filename = unique_filename(f'{safe_topic}.{link_type["ext"]}', used_names)
                with web_client.get(link, stream=True) as download:
                    with open(filename, 'wb') as file:
                        for chunk in download.iter_content(chunk_size=8192):
                            file.write(chunk)

        print('\n')

if __name__ == "__main__":
    main()
