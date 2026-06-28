# ciscoCollabCloudTools
Various Scripts and Utilities for managing Cisco Collaboration Cloud products

File | Purpose
--- | ---
user_roster.py | Lists the full user roster of your Control Hub org, grouped by admin role (with a non-admin bucket), including each user's creation date
licensed_users.py | Lists every license type in your Control Hub org along with the users assigned to each
dl_recordings.py | Mass-downloads all recordings and transcripts for one or more host users (requires admin scope for others' recordings)
space_closer.py | Utility that can be used to remove all members (including yourself) from multispaces, or find and remove yourself or close stale spaces
space_members.py | Simple script that outputs a CSV format of all members of a space
space_singlemods.py | Finds spaces you are part of that only have a single moderator
sync_spacemembers.py | Allows for comparison and sync of memberships between a Webex space and either an AD group or a file of email addresses
sync_teammembers.py | Allows for comparison and sync of memberships between a Webex team and an AD group
user_renamer.py | Allow easy changes to user names or email addresses (not applicable for Control Hub dirsync environments)
user_picgrabber.py | Downloads a Webex user's profile picture (avatar) to a PNG; accepts an email (same org) or a person ID (works for users outside your org)
user_spaces.py | Looks up a Webex user by email and lists every space they belong to (title, type, room ID) as CSV
user_orgid.py | Finds a Webex user's org ID by email (incl. users outside your org) via a 1:1 space membership, creating the 1:1 space if needed
user_personid.py | Finds a Webex user's person ID by email (incl. users outside your org) via a 1:1 space membership, creating the 1:1 space if needed
addusertoTeam.py | Adds a user (by email) to a Webex team given as a command-line argument; designed for scripted/bulk use
export_meetings.py | Exports scheduled meetings for a list of host users (from a file) to CSV over a forward date window

## Configuration

To keep non-portable and sensitive parameters (auth tokens, org IDs, directory credentials)
out of the code, every script reads them at runtime from a YAML file at:

```
~/Personal-Local/config.yml
```

(On Windows that resolves to `C:\Users\<you>\Personal-Local\config.yml`.)

Each script loads this file once and reads only the keys it needs. The full schema:

```yaml
wxteams:
  auth_token: <a Webex access token>   # required by every script that calls the Webex API
  org_id: <a Webex org id>             # optional; used by user_roster.py, licensed_users.py
                                       # and delete_users.py to target a specific org. If
                                       # omitted, the token's own org is used.

ldap:                                  # only needed by sync_spacemembers.py and
  server: <ad-server-hostname>         # sync_teammembers.py, for the Active Directory
  user: <bind-username>                # comparison
  password: <bind-password>
  basedn: <base-dn-for-users>
  basedn_groups: <base-dn-for-groups>
```

You only need the sections relevant to the scripts you run — e.g. if you never use the AD sync
scripts, omit the `ldap:` block entirely. (`wxtm_uclogin_decoder.py` works offline and needs no
config at all.)

`auth_token` may be either a short-lived (12-hour) personal developer token from
<https://developer.webex.com>, or — more conveniently — a long-lived, refreshable token issued
by an OAuth service-app / integration. Most operations act on other users in the org, so
whichever you use, the token must belong to a Control Hub administrator.
