"""
    janky.py - The swiss army jenkins knife for lazy programmers (me)
"""
import argparse
import configparser
import os.path
import signal
import sys
from jenkinsapi.jenkins import Jenkins


def main():
    """
        main - where the magic happens
    """
    opts = parse_commandline()
    build_params = {}
    b = None
    build_number = None
    signal.signal(signal.SIGINT, signal_handler)

    # Read the config file and connect to Jenkins
    (server, uid, token) = load_secrets()
    j = Jenkins(server, uid, token, lazy=True)
    buildjob = j[opts.jobname]

    # get the parameters for the build
    (b, build_number, build_params) = get_build_params(buildjob, opts.build_number, opts.last)

    # Print out the parameters
    if opts.list:
        print_params(build_params, b)

    # If we passed in some overriding parameters,
    # place them into our build parameters.
    if opts.params:
        print("\nOverriding the following parameters:", opts.params)
        for (key, value) in opts.params.items():
            build_params[key] = value

    # dump out the console
    # This may crash on unicode decode issues, use -s instead. They fixed it for
    # streaming the console, but not for just getting it.
    if opts.get_console:
        console_text = get_job_console(buildjob, build_number)
        print(console_text)

    # Kill off the specified build
    if opts.killbuild:
        kill_job(buildjob, build_number)

    # stream the console unless we're also launching, then that will take care of stream
    if opts.stream_console and not opts.fire:
        stream_console(job=buildjob, number=build_number)
        sys.exit()

    # Launch mode initiate!
    if opts.fire:
        launch_build(buildjob, build_params, opts.stream_console)


def get_build_params(buildjob, buildnumber, last):
    """
        Get the build parameters from the last job, a specific job or the defaults

    """
    b = None
    build_params = {}
    build_number = buildnumber

    # get the params from the last job
    if last:
        b = buildjob.get_last_build()
        build_params = b.get_params()
        build_number = b.get_number()

    # get the params from a specific job number
    elif build_number:
        b = buildjob.get_build(build_number)
        build_params = b.get_params()

    # Get the job default parameters
    else:
        for parm in buildjob.get_params():
            key = parm["defaultParameterValue"]["name"]
            value = parm["defaultParameterValue"]["value"]
            build_params[key] = value

    return(b, build_number, build_params)


def print_params(build_params, b):
    """
        Prints out the build parameters
    """
    if b:
        print("\nParameters for:", b)
    else:
        print("\nDefault job parameters:")

    for (key, value) in build_params.items():
        print(key + ":", value)


def launch_build(job, params, stream):
    """
        Start a build with parameters
    """
    qi = job.invoke(build_params=params)
    b = qi.get_job()
    print_params(qi.get_parameters(), b)
    print('\nBuild:', b, "waiting to start...")

    build = qi.block_until_building()
    print(build, "started")
    if stream:
        stream_console(build=build)


def get_artifacts(job, number):
    """
        Look up the build number and get the artifacts
    """
    build = job.get_build(number)

    artifacts = build.get_artifacts()
    for art in artifacts:
        print(art.filename, art.url, art.build)
    return artifacts


def kill_job(job, number):
    """
        Look up the build number and stop it
    """
    if not number:
        print("\nJob number not specified. Nothing to cancel.")
        return

    build = job.get_build(number)

    if build.is_running():
        print("Cancelling build", build)
        build.stop()
        build.block_until_complete()
        print(f"Build {build} cancelled")
    else:
        print(build, "was not running and couldn't be cancelled")


def get_job_console(job, number):
    """
        Look up the build number and grab the console
    """
    build = job.get_build(number)

    return build.get_console()


def stream_console(job=None, number=None, build=None):
    """
        Look up the build number and grab the console
    """
    if job:
        build = job.get_build(number)

    for line in build.stream_logs():
        print(line)
    return "Console stream complete"


def connect_to_jenkins():
    """
        Makes connection to Jenkins server
    """
    (server, uid, token) = load_secrets()
    return Jenkins(server, uid, token)


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


def parse_params(params):
    """
    Parses the comma separated key:value pairs in the params string

        Returns:
            a dictionary containing the key:value pairs
    """
    parsed_params = {}

    if params:
        param_pairs = params.split(',')
        for parm in param_pairs:
            if ':' in parm:
                (key, value) = parm.split(':')
                # Fix up Bools if needed
                match value.lower():
                    case "true":
                        value = True
                    case "false":
                        value = False

                parsed_params[key] = value

    return parsed_params


def parse_commandline():
    """
    Parses command line and returns options object.

        Returns:
            options (object): Object containing all of the program options set
            on the command line
    """
    parser = argparse.ArgumentParser(prog="launch_build.py", description= """ """)

    # add in command line options
    parser.add_argument("-c", "--console", dest="get_console",
                        action='store_true',
                        help="Dump out the console text",
                        default=False)
    parser.add_argument("-j", "--jobname", dest="jobname",
                        help="Name of Jenkins job to run",
                        default=None)
    parser.add_argument("-k", "--kill", dest="killbuild",
                        help="Kill build specified by -n",
                        action='store_true',
                        default=None)
    parser.add_argument("-n", "--number", dest="build_number",
                        help="Build number to kill or use parameters from",
                        type=int,
                        default=None)
    parser.add_argument("-l", "--list", dest="list",
                        action='store_true',
                        help="List out parameters for specified build or job defaults",
                        default=False)
    parser.add_argument("-p", "--params", dest="params",
                        help="Param changes in the form key:value,key2:value",
                        default=None)
    parser.add_argument("-s", "--stream", dest="stream_console",
                        action='store_true',
                        help="Stream the console for a job, or after build is launched",
                        default=False)
    parser.add_argument("-t", "--last", dest="last",
                        action='store_true',
                        help="Use last job as parameter source",
                        default=False)
    parser.add_argument("-x", "--exec", dest="fire",
                        action='store_true',
                        help="Execute job with specified parameters",
                        default=False)

    options = parser.parse_args()

    # Parse the build parameter overrides into a dict
    if options.params:
        options.params = parse_params(options.params)

    return options


def signal_handler(sig, frame):
    """
        Make aborts not barf all over the place
    """
    # print(sig, frame)
    print('\nAborted.')
    sys.exit(0)


if __name__ == "__main__":
    main()
