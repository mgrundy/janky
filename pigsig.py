#!/usr/bin/env python3
"""
pigsig - Pipeline Signaller

Text-based pipeline status checker with downstream job number discovery.
A simple example for jenkinslight.py

Filename: pigsig.py

Author: Michael Grundy <grundyisland@gmail.com>
Copyright (c) 2022-2026 Michael Grundy
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import argparse
import configparser
import datetime
import os
import sys

# if Python 3.10 or higher we can use the system keychain (or equiv on other platforms)
if sys.version_info.major >= 3 and sys.version_info.minor >= 10:
    import truststore
    truststore.inject_into_ssl()

from jenkinslight import JenkinsLight


def main():
    """
        main - where the magic happens
    """
    opts = parse_commandline()

    # Read the config file and connect to Jenkins
    (server, uid, token) = load_secrets()
    j = JenkinsLight(server, uid, token, timeout=60)

    if not opts.jobname:
        print("You have to specify at least one job.")
        sys.exit(3)

    if not opts.subjob:
        print("You must specify a subjob to track with -s/--subjob")
        sys.exit(3)

    jobs = opts.jobname.split(",")

    for jobname in jobs:
        view_data = j.get_pipeline_data(jobname, None)
        line_limit = int(opts.limit) if opts.limit else 999

        # Print job header
        display_name = jobname.replace('/job/', '/')
        print(f'{display_name}: {j.baseurl}/job/{jobname}')
        print()

        for job in view_data:
            if opts.limit and line_limit <= 0:
                break
            line_limit -= 1

            jobtime = datetime.datetime.fromtimestamp(job["startTimeMillis"]/1000.0)
            date = jobtime.strftime("%Y-%m-%d %H:%M:%S")

            status = job["status"]
            job_id = job["name"]

            # Get test results if available
            results_string = ""
            try:
                result_data = j.get_pipeline_results(jobname, job["id"])
                results_string = f"Passed: {result_data['passCount']}, Failed: {result_data['failCount']}, Skipped: {result_data['skipCount']}"
            except Exception:
                results_string = "No test results"

            # Get fingerprints to find downstream job numbers
            subjob_number = ""
            try:
                fingerprints = j.get_fingerprints(jobname, job["id"])
                # Filter for the specified subjob and extract build numbers
                subjob_numbers = [fp['owner_build_number'] for fp in fingerprints
                                  if fp['owner_job'] == opts.subjob and fp['owner_build_number']]
                if subjob_numbers:
                    subjob_number = ", ".join([str(num) for num in subjob_numbers])
            except Exception:
                pass

            # Print job information
            print(f"Job: {job_id}")
            print(f"  Date: {date}")
            print(f"  Status: {status}")
            print(f"  Results: {results_string}")
            if subjob_number:
                print(f"  {opts.subjob}: {subjob_number}")
            else:
                print(f"  {opts.subjob}: No run found")
            print()


def load_secrets():
    """
        Reads config file returns (server, userid, personal access token)
    """
    cfgfile = 'janky.cfg'
    if not os.path.isfile(cfgfile):
        raise ValueError("Config file does not exist")
    cfg = configparser.ConfigParser()
    cfg.read(cfgfile)
    sections = cfg.sections()
    # Could have a parameter for a specific section, but whatever.
    sector = sections[0]
    uname = cfg[sector]['uname']
    token = cfg[sector]['token']
    server = cfg[sector]['server']

    return (server, uname, token)


def parse_commandline():
    """
    Parses command line and returns options object.

        Returns:
            options (object): Object containing all of the program options set
            on the command line
    """
    parser = argparse.ArgumentParser(
        prog="pigsig.py",
        description="Pipeline Integrity Signaller - Simple pipeline status with downstream job tracking"
    )

    # add in command line options
    parser.add_argument("-j", "--jobname", dest="jobname",
                        help="Name of Jenkins job pipeline to view",
                        default=None)
    parser.add_argument("-l", "--limit", dest="limit",
                        help="Limit the number of builds to display",
                        default=None)
    parser.add_argument("-s", "--subjob", dest="subjob",
                        help="Name of downstream subjob to track (required)",
                        default=None)

    options = parser.parse_args()

    # Fixup jobname if in a folder
    if options.jobname and '/' in options.jobname:
        options.jobname = options.jobname.replace('/', '/job/')

    return options


if __name__ == "__main__":
    main()
