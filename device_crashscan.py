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
Scans RoomOS devices in a Control Hub org for crash evidence and reports it as CSV.

RoomOS does not expose crash-dump files through the cloud APIs (those only exist in the
device's local web interface / log bundles), but it does expose the signals that indicate a
device has crashed:

  * SystemUnit LastShutdownReason -- "Unknown" means the device went down without a clean
    shutdown (application crash, kernel panic, watchdog reset or power loss), versus the
    normal reasons (Restart, Shutdown, Upgrade, Standby, FirstBoot, ...)
  * SystemUnit LastShutdownTime / Uptime -- when that happened and how long it has been up
  * Diagnostics Message -- any active diagnostics the device is reporting
  * errorCodes -- Control Hub's own issue list, returned with the device record

Devices can be scoped by software channel (--channel stable/beta/...), device type (--type,
default roomdesk), product (--product, wildcards allowed) and/or display name (--name).
By default only devices with crash evidence (an abnormal shutdown or active error-level
diagnostics) are output; use --all to include every device scanned. Offline devices cannot
answer xAPI queries and are reported to stderr as skipped.

Usage examples:
  device_crashscan.py                                  scan all roomdesk devices
  device_crashscan.py --channel beta                   only devices on the beta channel
  device_crashscan.py --product "*Desk*" --all         all Desk devices, crashed or not
  device_crashscan.py --name "Lobby*" -o crashes.csv   name-filtered, written to a file

Requires an auth token with the spark:xapi_statuses scope (not included in spark:all --
it must be added to the integration explicitly) plus admin device access
(spark-admin:devices_read) against the Webex Control Hub org.
"""

import argparse
import csv
import fnmatch
import os
import sys
from time import sleep

import requests
import yaml

# specifies separate config file containing non-portable parameters
# looks for a YAML file in the user's home directory under the subfolder "Personal-Local"
# i.e. c:\users\jsmith\Personal-Local\config.yml
CONFIG_FILE = os.path.join(os.path.expanduser('~'), "Personal-Local", "config.yml")

BASE_URL = 'https://webexapis.com/v1'
PAGE = 100
TIMEOUT = 30

# LastShutdownReason values that indicate a clean, explained shutdown; anything else
# (notably "Unknown") means the device went down unexpectedly
CLEAN_SHUTDOWNS = {'firstboot', 'restart', 'shutdown', 'upgrade', 'standby',
                   'modifysecuritypersistency', 'factoryreset', 'converttocloud'}

CSV_HEADER = ['displayName', 'product', 'type', 'software', 'upgradeChannel',
              'connectionStatus', 'abnormalShutdown', 'lastShutdownReason',
              'lastShutdownTime', 'uptimeDays', 'diagnostics', 'errorCodes']

def api_get(session, url, params=None):
    """GET against the API, retrying on rate limiting (honoring Retry-After)"""
    while True:
        response = session.get(url, params=params, timeout=TIMEOUT)
        if response.status_code == 429:
            try:
                wait = max(int(response.headers.get('Retry-After', 1)), 1)
            except ValueError:
                wait = 1
            print(f'server busy, retrying in {wait}s...', file=sys.stderr)
            sleep(wait)
            continue
        return response

def list_devices(session, device_type):
    """list org devices (optionally server-side filtered by type), following pagination"""
    devices = []
    params = {'max': PAGE}
    if device_type and device_type.lower() != 'any':
        params['type'] = device_type
    start = 0
    while True:
        params['start'] = start
        response = api_get(session, f'{BASE_URL}/devices', params)
        if response.status_code != 200:
            print(f'### Device list failed: {response.status_code}: '
                  f'{response.content.decode("utf-8")}', file=sys.stderr)
            raise SystemExit(1)
        items = response.json().get('items', [])
        if not items:
            break
        devices.extend(items)
        if len(items) < PAGE:
            break
        start += len(items)
    return devices

def name_match(value, pattern):
    """case-insensitive match: wildcard pattern if it contains */?, else substring"""
    value = (value or '').lower()
    pattern = pattern.lower()
    if '*' in pattern or '?' in pattern:
        return fnmatch.fnmatch(value, pattern)
    return pattern in value

def matches_filters(device, args):
    """apply the channel / product / name filters (client-side)"""
    if args.channel and (device.get('upgradeChannel') or '').lower() != args.channel.lower():
        return False
    if args.product and not name_match(device.get('product'), args.product):
        return False
    if args.name and not name_match(device.get('displayName'), args.name):
        return False
    return True

def xapi_status(session, device_id, name):
    """query a device xStatus path via the cloud xAPI; returns the result dict or None"""
    response = api_get(session, f'{BASE_URL}/xapi/status',
                       {'deviceId': device_id, 'name': name})
    if response.status_code != 200:
        return None
    return response.json().get('result', {})

def scan_device(session, device):
    """query one device's crash signals; returns a CSV row dict, or None if unreachable"""
    system_unit = xapi_status(session, device['id'], 'SystemUnit.*')
    if system_unit is None:
        return None
    system_unit = system_unit.get('SystemUnit', {})

    reason = system_unit.get('LastShutdownReason', '')
    uptime_secs = system_unit.get('Uptime')

    # active diagnostics, e.g. [{'id': 1, 'Description': ..., 'Level': ..., 'Type': ...}]
    diagnostics = (xapi_status(session, device['id'], 'Diagnostics.*') or {})
    messages = (diagnostics.get('Diagnostics') or {}).get('Message') or []
    diagnostics_text = '; '.join(
        f'{message.get("Level", "?")}: {message.get("Type", "?")}: '
        f'{message.get("Description", "")}'
        for message in messages if isinstance(message, dict))
    has_error_diag = any((message.get('Level') or '').lower() in ('error', 'critical')
                         for message in messages if isinstance(message, dict))

    abnormal = bool(reason) and reason.lower() not in CLEAN_SHUTDOWNS
    return {
        'displayName': device.get('displayName', ''),
        'product': device.get('product', ''),
        'type': device.get('type', ''),
        'software': device.get('software', ''),
        'upgradeChannel': device.get('upgradeChannel', ''),
        'connectionStatus': device.get('connectionStatus', ''),
        'abnormalShutdown': 'yes' if abnormal else 'no',
        'lastShutdownReason': reason,
        'lastShutdownTime': system_unit.get('LastShutdownTime', ''),
        'uptimeDays': round(uptime_secs / 86400, 1) if isinstance(uptime_secs, int) else '',
        'diagnostics': diagnostics_text,
        'errorCodes': '; '.join(device.get('errorCodes') or []),
        '_crash_evidence': abnormal or has_error_diag,
    }

def main():
    """scan filtered RoomOS devices for crash evidence and output CSV"""
    parser = argparse.ArgumentParser(
        description='Scan RoomOS devices in a Control Hub org for crash evidence '
                    '(abnormal shutdowns, active diagnostics) and report as CSV.')
    parser.add_argument('--channel',
                        help='filter by software channel, e.g. stable, beta, preview, latest')
    parser.add_argument('--type', default='roomdesk',
                        help='device type filter (default: roomdesk; use "any" for all types)')
    parser.add_argument('--product',
                        help='filter by product, substring or wildcards, e.g. "*Desk Pro"')
    parser.add_argument('--name',
                        help='filter by display name, substring or wildcards, e.g. "Lobby*"')
    parser.add_argument('--all', action='store_true',
                        help='output every device scanned, not just those with crash evidence')
    parser.add_argument('-o', '--output', help='write CSV to this file (default: stdout)')
    args = parser.parse_args()

    with open(CONFIG_FILE, 'r') as config_file:
        config_params = yaml.safe_load(config_file)

    wxteams_config = config_params['wxteams']
    wxteams_token = wxteams_config['auth_token']

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {wxteams_token}"})

    print('Listing devices...', file=sys.stderr)
    devices = list_devices(session, args.type)
    matched = [device for device in devices if matches_filters(device, args)]
    print(f'{len(matched)} of {len(devices)} device(s) match the filter.', file=sys.stderr)

    online = [device for device in matched
              if (device.get('connectionStatus') or '').startswith('connected')]
    skipped = len(matched) - len(online)
    if skipped:
        print(f'Skipping {skipped} offline device(s) (cannot answer xAPI queries).',
              file=sys.stderr)

    rows = []
    for count, device in enumerate(online, 1):
        print(f'  [{count}/{len(online)}] scanning {device.get("displayName", device["id"])}...',
              file=sys.stderr)
        row = scan_device(session, device)
        if row is None:
            print(f'### could not query {device.get("displayName", device["id"])}, skipping '
                  '(check the token has the spark:xapi_statuses scope)', file=sys.stderr)
            continue
        if args.all or row['_crash_evidence']:
            rows.append(row)

    out = open(args.output, 'w', newline='', encoding='utf-8') if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=CSV_HEADER, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()

    flagged = sum(1 for row in rows if row['_crash_evidence'])
    print(f'\n{flagged} device(s) with crash evidence '
          f'({len(rows)} row(s) written).', file=sys.stderr)

if __name__ == "__main__":
    main()
