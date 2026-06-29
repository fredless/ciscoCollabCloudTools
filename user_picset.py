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
Sets a Webex user's profile picture (avatar) from a local PNG file.

Usage: user_picset.py <user_email> <png_file>

Webex sets an avatar from a downloadable URL, not inline image data, so this uploads the PNG to
tmpfiles.org (a no-account host that auto-deletes the file after about an hour) and points the
avatar at the resulting direct-download URL.

The Webex People update is a full replace -- every field must be present in the request or the
omitted ones get cleared. So this first GETs the person's full details, then PUTs all existing
values back together with the new avatar URL.

Requires an auth token from a user with admin privileges against the Webex Control Hub org.
"""

import os
import re
import sys

import requests
import yaml
from webexpythonsdk import WebexAPI, ApiError

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

# PNG file signature, used to sanity-check the supplied file
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

# Webex sets avatars from a fetchable URL, so the PNG is uploaded here first. tmpfiles.org is a
# no-account host that auto-deletes after about an hour; swap this if you prefer another host.
TMPFILES_UPLOAD_URL = 'https://tmpfiles.org/api/v1/upload'

# Existing updatable person fields to carry over unchanged on the PUT, so none get blanked (the
# People update replaces the whole person). Only fields actually present are included. Note:
# phoneNumbers is handled separately below, since the PUT accepts only the "work" type while a
# GET can also return mobile/fax/extension entries that would be rejected.
PRESERVE_FIELDS = ['emails', 'extension', 'locationId', 'displayName', 'firstName', 'lastName',
                   'orgId', 'roles', 'licenses', 'department', 'manager', 'managerId', 'title',
                   'addresses', 'siteUrls', 'loginEnabled']

def valid_smtp(email):
    """check if email is valid URI syntax"""
    regex_check = r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,})+$'
    if not re.search(regex_check, email):
        print('### Provided email is not a valid address format ###')
        return False
    return True

def upload_png(png_bytes, filename):
    """upload a PNG to tmpfiles.org and return a direct-download URL Webex can fetch"""
    response = requests.post(TMPFILES_UPLOAD_URL,
                             files={'file': (filename, png_bytes, 'image/png')})
    response.raise_for_status()
    page_url = response.json()['data']['url']
    # tmpfiles returns a viewer URL (https://tmpfiles.org/<id>/<name>); the direct-download form
    # inserts /dl/ after the host. Normalise to https while we're at it.
    page_url = page_url.replace('http://', 'https://', 1)
    return page_url.replace('https://tmpfiles.org/', 'https://tmpfiles.org/dl/', 1)

def main():
    """set a user's avatar from a PNG file"""
    if len(sys.argv) != 3:
        print('Usage: user_picset.py <user_email> <png_file>')
        sys.exit(1)

    user_email = sys.argv[1].strip()
    png_file = sys.argv[2].strip()

    if not valid_smtp(user_email):
        sys.exit(1)

    # read the PNG bytes to upload as the new avatar
    try:
        with open(os.path.expanduser(png_file), 'rb') as handle:
            png_bytes = handle.read()
    except OSError as error:
        print(f'### Could not read PNG file: {error} ###')
        sys.exit(1)

    if not png_bytes.startswith(PNG_SIGNATURE):
        print(f'### {png_file} does not look like a PNG file ###')
        sys.exit(1)

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
        print(error)
        if error.status_code == 401:
            print('### Please check that a fresh auth_token has been specified in config file. ###')
        sys.exit(1)

    matches = list(api.people.list(email=user_email))
    if not matches:
        print('### no matching users found with that email address ###')
        sys.exit(1)

    # GET the full person record so every existing field can be re-sent on the PUT
    person = api.people.get(matches[0].id).to_dict()

    print(f'Setting avatar for {person.get("displayName")} ({user_email})...')

    # upload the PNG to a temporary public URL Webex can download the avatar from
    try:
        avatar_url = upload_png(png_bytes, os.path.basename(png_file))
    except (requests.RequestException, KeyError, ValueError) as error:
        print(f'### Failed to upload PNG to temporary host: {error} ###')
        sys.exit(1)

    # carry over all existing updatable fields, then overlay the new avatar URL
    payload = {field: person[field] for field in PRESERVE_FIELDS if person.get(field) is not None}

    # phoneNumbers: the PUT accepts only "work"-type entries (type/value), whereas a GET can
    # return mobile/fax/extension types that would be rejected, so keep just the work numbers
    work_numbers = [{'type': number['type'], 'value': number['value']}
                    for number in (person.get('phoneNumbers') or [])
                    if number.get('type') == 'work' and number.get('value')]
    if work_numbers:
        payload['phoneNumbers'] = work_numbers

    payload['avatar'] = avatar_url

    try:
        api.people.update(person['id'], **payload)
    except ApiError as error:
        if error.status_code == 403:
            print('### Forbidden: updating a user requires auth_token to be a full admin token '
                  'with the spark-admin:people_write scope. ###')
        else:
            print(f'### Failed to update avatar: {error} ###')
        sys.exit(1)

    print(f'Avatar updated for {person.get("displayName")} ({user_email}).')

if __name__ == "__main__":
    main()
