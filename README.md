# ciscoCollabCloudTools
Various Scripts and Utilities for managing Cisco Collaboration Cloud products

File | Purpose
--- | ---
user_roster.py | Lists the full user roster of your Control Hub org, grouped by admin role (with a non-admin bucket), including each user's creation date
licensed_users.py | Lists every license type in your Control Hub org along with the users assigned to each
space_closer.py | Utility that can be used to remove all members (including yourself) from multispaces, or find and remove yourself or close stale spaces
space_members.py | Simple script that outputs a CSV format of all members of a space
space_singlemods.py | Finds spaces you are part of that only have a single moderator
sync_spacemembers.py | Allows for comparison and sync of memberships between a Webex space and either an AD group or a file of email addresses
sync_teammembers.py | Allows for comparison and sync of memberships between a Webex Teams team, and an AD group
user_renamer.py | Allow easy changes to user names or email addresses (not applicable for Control Hub dirsync environments)
