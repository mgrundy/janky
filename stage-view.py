"""
Text Mode Jenkins Stage View
"""
import argparse
import configparser
import datetime
import json
import os
import sys
# if Python 3.10 or higher we can use the system keychain (or equiv on other platforms)
if sys.version_info.major >= 3 and sys.version_info.minor >= 10:
    import truststore
    truststore.inject_into_ssl()

#from jenkinsapi.jenkins import Jenkins
from rich.align import Align
from rich.console import Console, Group
from rich.columns import Columns
from rich.panel import Panel
from rich.style import Style

from jenkinslight import JenkinsLight

job_colors = {}
job_colors["SUCCESS"] = "bright_green"
job_colors["IN_PROGRESS"] = "yellow"
job_colors["ABORTED"] = "grey50"
job_colors["UNSTABLE"] = "bright_red"
job_colors["FAILED"] = "red3"
job_colors["NOT_EXECUTED"] = "purple"
#job_colors[""]



def main():
    """
        main - where the magic happens
    """
    opts = parse_commandline()
    jobs_hash = {}
    # Read the config file and connect to Jenkins
    (server, uid, token) = load_secrets()
    j = JenkinsLight(server, uid, token)

    if not opts.jobname:
        print("You have to specify at least one job.")
        sys.exit(3)
    jobs = opts.jobname.split(",")

    console = Console()

    for jobname in jobs:
        view_data = j.get_pipeline_data(jobname, opts.filename)
        line_limit = int(opts.limit) if opts.limit else 999
        display_name = jobname.replace('/job/', '/')
        console.print(f'[b][white]{display_name}[/b]: [blue]{j.baseurl}/job/{jobname}[/blue]')

        jobs_hash[jobname] = []

        for job in view_data:
            if opts.limit and line_limit <= 0:
                break
            line_limit -= 1

            stages = job["stages"]
            jobs_hash[jobname].append(job["id"])

            jobtime = datetime.datetime.fromtimestamp(job["startTimeMillis"]/1000.0)
            date = jobtime.strftime("%b %d")
            time = jobtime.strftime(" %H:%M")

            duration = time_str(job["durationMillis"])
            statcolor = job_colors[job["status"]]
            job_string1 = f'[{statcolor}]{job["status"]}'
            job_string2 = f'[white]{date}'
            job_string3 = f'[blue]{time}'

            job_renderables = [
                Panel(
                    Group(
                        # Align.center(" "),
                        Align.center(job_string1),
                        Align.center(job_string2),
                        Align.center(job_string3),
                        # Align.center(" "),
                    ),
                    width=15,
                    height=6,
                    title=f'[white]{job["name"]}',
                    subtitle=f"[cyan]{duration}",
                    border_style=statcolor,
                )
            ]
            job_renderables.extend(
                [
                    Panel(
                        get_content(stage),
                        width=15,
                        height=6,
                        expand=True,
                        border_style=job_colors[stage["status"]],
                    )
                    for stage in stages
                ]
            )

            console.print(Columns(job_renderables))

    if opts.resultfname is not None:
        j = json.dumps(jobs_hash, indent=4, ensure_ascii=False)
        with open(opts.resultfname, 'w', encoding="utf-8") as output_file:
            output_file.write(j)

def time_str(millis, short=False):
    """Formats millis into hours, minutes, seconds

    Args:
        millis (_type_): value to convert to time sting
        short (bool, optional): Only return minutes and seconds (will truncate). Defaults to False.

    Returns:
        _type_: String
    """
    seconds=(millis/1000)%60
    seconds = int(seconds)
    minutes=(millis/(1000*60))%60
    minutes = int(minutes)
    hours=(millis/(1000*60*60))%24
    hours=int(hours)
    ms_string = f'{minutes:02d}:{seconds:02d}'
    h_string = f'{hours:02d}:'
    if short is True:
        return ms_string
    return h_string + ms_string


def get_content(stage):
    """Extract text from user dict."""
    #print(stage)
    status = stage["status"]
    name = stage["name"]
    time = time_str(stage["durationMillis"])

    return f'[b][white]{name}[/b]\n[{job_colors[stage["status"]]}]{status}\n[cyan]{time}'


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
    #['mobilecicd']
    uname = cfg[sector]['uname']
    token = cfg[sector]['token']
    server = cfg[sector]['server']

    return(server, uname, token)


def parse_commandline():
    """
    Parses command line and returns options object.

        Returns:
            options (object): Object containing all of the program options set
            on the command line
    """
    parser = argparse.ArgumentParser(
        prog="stage-view.py", description=""" Jenkins status from the shell."""
    )

    # add in command line options
    parser.add_argument("-f", "--filename", dest="filename",
                        help="Name of file to save pipeline json to",
                        default=None)
    parser.add_argument("-rf", "--results", dest="resultfname",
                        help="Name of file to save run # and names to",
                        default=None)
    parser.add_argument("-j", "--jobname", dest="jobname",
                        help="Name of Jenkins job pipeline to view",
                        default=None)
    parser.add_argument("-l", "--limit", dest="limit",
                        help="Limit the number of lines",
                        default=None)

    options = parser.parse_args()

    # Fixup jobname if in a folder
    if options.jobname and '/' in options.jobname:
        options.jobname = options.jobname.replace('/', '/job/')

    return options


if __name__ == "__main__":
    main()
