# Copyright (C) 2019 Frederick W. Nielsen
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
Simple script to decode uclogin.log file(s) using substitute coded entries from ced.dat
Use current working path, or takes a single argument for an alternative path where ced.dat
and uclogin.log file(s) should already be
"""

import json
import glob
import os
import sys

OUT_FOLDER = 'decoded'
CED_FILE = 'ced.dat'
FILESPEC = 'uclogin.log*'

def main():
    # change to new directory if passed as argument
    if sys.argv[1:]:
        os.chdir(sys.argv[1:][0])

    # Build list of target files
    files_list = glob.glob(FILESPEC)
    if files_list:
        # load decoder ring into dict
        with open(CED_FILE, 'r') as ced_contents:
            decoder = json.load(ced_contents)

        # make output folder
        os.makedirs(OUT_FOLDER, exist_ok=True)

        counter = 1
        # iterate through each uclogin log file found
        for filename in files_list:
            print('parsing file #' + str(counter) + " of " + str(len(files_list)))
            # read decoded file
            with open(filename, 'r') as file:
                contents = file.read()
            # decode
            for secret, value in decoder.items():
                contents = contents.replace('{!' + secret + '!}', value)
            # write decoded result
            with open('/'.join((OUT_FOLDER, filename)), 'w') as file:
                file.write(contents)
            counter += 1

if __name__ == "__main__":
    main()
