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
Mass-downloads all recordings and transcripts for one or more host users, prompting for how
many days back to search. Requires admin scope to access recordings other than your own.
"""

import itertools
import os
import re
import shutil
from datetime import datetime, timedelta, timezone

import requests
import yaml
from webexpythonsdk import ApiError, WebexAPI

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

SPINNER = itertools.cycle(['-', '/', '|', '\\'])

# download link keys returned by the API and the extension to save each download as
LINK_TYPES = [{'key': 'recordingDownloadLink', 'ext': 'mp4'},
              {'key': 'transcriptDownloadLink', 'ext': 'vtt'}]

PAGE = 100

# the recordings API defaults to a recent window when from/to are omitted and caps any single
# listing query at a 30-day span, so longer ranges are queried in windows
WINDOW_DAYS = 30
DEFAULT_DAYS_BACK = 365

def print_status(text, linefeed=0):
    """output status line"""
    text = f'{next(SPINNER)} {text}'
    screen_width = shutil.get_terminal_size((80, 0))[0]
    print(text +
          ' ' * (screen_width-(len(text)+1)) +
          '\b' * (screen_width -1) +
          '\n' * linefeed,
          end='')

def sdk_list_recordings(api, params):
    """list recordings through the SDK session, yielding Recording objects

    Works around a webexpythonsdk bug (still present in 2.0.6): recordings.list()
    rejects any call that omits integrationTag (check_type missing optional=True) and
    sends max as a bogus max_recordings query param. This does exactly what that method
    does after its argument handling, so the SDK session still provides pagination and
    rate-limit (429) retries.
    """
    for item in api._session.get_items('recordings', params=params):
        yield api._object_factory('recording', item)

def list_recordings(api, user, days_back):
    """return all recordings for a host over the range, or None on an API error

    Steps back through the range one 30-day window at a time (the API's per-query limit);
    the SDK follows the pagination links within each window.
    """
    recordings = {}
    window_end = datetime.now(timezone.utc)
    oldest = window_end - timedelta(days=days_back)
    while window_end > oldest:
        window_start = max(window_end - timedelta(days=WINDOW_DAYS), oldest)
        params = {'max': PAGE,
                  'hostEmail': user,
                  'from': window_start.isoformat(timespec='seconds'),
                  'to': window_end.isoformat(timespec='seconds')}
        try:
            for item in sdk_list_recordings(api, params):
                # adjacent windows meet exactly at their boundary, so dedupe by id
                recordings[item.id] = item
        except ApiError as error:
            print(f'### could not list recordings: {error}')
            return None
        window_end = window_start
    return list(recordings.values())

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
        config_params = yaml.safe_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    users_input = input('Enter host email(s) to download recordings for (comma-separated): ')
    users = [email.strip() for email in users_input.split(',') if email.strip()]
    if not users:
        print('### No host emails provided, exiting.')
        exit()

    days_input = input(f'How many days back to search? [{DEFAULT_DAYS_BACK}]: ').strip()
    try:
        days_back = int(days_input) if days_input else DEFAULT_DAYS_BACK
    except ValueError:
        print('### Invalid number of days, exiting.')
        exit()

    # https://github.com/WebexCommunity/WebexPythonSDK/ abstracts most of the work,
    # including pagination and rate-limit (429) retries
    api = WebexAPI(access_token=wxteams_token)

    # the temporary direct download links are pre-signed plain-file URLs outside the API,
    # so the media transfers themselves stay on a requests session
    web_client = requests.Session()

    # track names already written so same-topic recordings don't overwrite each other
    used_names = set()

    for user in users:
        print(f'Retrieving recording list for {user}...')
        items = list_recordings(api, user, days_back)

        if items is None:
            continue

        if not items:
            print(f'{user} has no recordings.\n')
            continue

        print(f'{user} has {len(items)} recording(s)...')
        for count, summary in enumerate(items, 1):
            print_status(f'Downloading recording {count} of {len(items)}...')
            try:
                details = api.recordings.get(summary.id)
            except ApiError as error:
                print(f'### could not get details for {summary.id}: {error}')
                continue
            # the SDK's Recording model doesn't expose temporaryDirectDownloadLinks as a
            # property, so read it from the raw payload
            links = details.json_data.get('temporaryDirectDownloadLinks') or {}
            if not links:
                # e.g. a recording still transcoding, or with no downloadable content
                continue

            # name files after the recording topic, sanitized for the filesystem
            topic = details.topic or summary.id
            safe_topic = re.sub(r'[^\w\-. ]', '_', topic).strip() or summary.id

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
