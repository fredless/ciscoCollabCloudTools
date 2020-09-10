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

def main():
    # change to new directory if passed as argument
    if sys.argv[1:]:
        os.chdir(sys.argv[1:][0])

    # Build list of target files
    file_list = glob.glob("uclogin.log*")
    if file_list:
        # load decoder ring
        with open("ced.dat", "r") as cedfile:
            decoder = json.load(cedfile)

        # make output folder
        os.makedirs(OUT_FOLDER, exist_ok=True)

        # iterate through each uclogin log file found
        counter = 1
        for filename in file_list:
            print('parsing file #' + str(counter) + " of " + str(len(file_list)))
            # read file contents into memory
            with open(filename, "r") as in_file:
                contents = in_file.read()
            # decode
            for secret, value in decoder.items():
                contents = contents.replace('{!' + secret + '!}', value)
            # write decoded file
            with open(OUT_FOLDER + '/' + filename, "w") as out_file:
                out_file.write(contents)

if __name__ == "__main__":
    main()
