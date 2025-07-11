"""
    janky.py - The swiss army jenkins knife for lazy programmers (me)
"""
import argparse
import configparser
import os.path
import signal
import sys
import time
import xmltodict

# if Python 3.10 or higher we can use the system keychain (or equiv on other platforms)
if sys.version_info.major >= 3 and sys.version_info.minor >= 10:
    import truststore
    truststore.inject_into_ssl()

from jenkinsapi.jenkins import Jenkins


def main():
    """
        main - where the magic happens
    """
    build = None
    build_number = None
    build_params = {}

    # Make ctrl+C less vomitty.
    signal.signal(signal.SIGINT, signal_handler)

    # Basic setup bits, get cli options, get auth info, connect
    # to jenkins and grab the job object.
    opts = parse_commandline()
    (server, uid, token) = load_secrets()

    try:
        j = Jenkins(server, uid, token, lazy=True)

    except Exception as e:
        eprint(e)
        print("Failed building Jenkins connection")
        sys.exit(1)

    try:
        buildjob = j[opts.jobname]
    except Exception as e:
        eprint(e)
        print("Unknown Job: ", opts.jobname)
        sys.exit(1)

    # get the parameters for the build
    try:
        (build, build_number, build_params) = get_build_params(buildjob, opts.build_number, opts.last)

    except Exception as e:
        eprint(e)
        print("Failed getting build params")
        sys.exit(1)

    # Print out the parameters
    if opts.list:
        print_params(build_params, build)

    # If we passed in some overriding parameters,
    # place them into our build parameters.
    if opts.params: 
        if opts.update_job:
            update_defaults(buildjob, opts.params)

        else:
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
        kill_job(buildjob, build_number, opts.stream_console)

    # stream the console unless we're also launching, then that will take care of stream
    if opts.stream_console and not (opts.fire or opts.killbuild):
        stream_console(job=buildjob, number=build_number)
        sys.exit(0)

    # Launch mode initiate!
    if opts.fire:
        launch_build(buildjob, build_params, opts.stream_console)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def get_build_params(buildjob, buildnumber, last):
    """
        Get the build parameters from the last job, a specific job or the defaults

    """
    build = None
    build_params = {}
    build_number = buildnumber

    # get the params from the last job
    if last:
        build = buildjob.get_last_build()
        build_params = build.get_params()
        build_number = build.get_number()

    # get the params from a specific job number
    elif build_number:
        build = buildjob.get_build(build_number)
        build_params = build.get_params()

    # Get the job default parameters
    else:
        for parm in buildjob.get_params():
            key = parm["defaultParameterValue"]["name"]
            value = parm["defaultParameterValue"]["value"]
            build_params[key] = value

    return (build, build_number, build_params)


def print_params(build_params, build):
    """
        Prints out the build parameters
    """
    if build:
        print("\nParameters for:", build)
    else:
        print("\nDefault job parameters:")

    for (key, value) in build_params.items():
        print(key + ":", value)


def launch_build(job, params, stream):
    """
        Start a build with parameters
    """
    default_retries = 3

    try:
        qi = job.invoke(build_params=params)
    except Exception as e:
        eprint(e)
        eprint("Failed during Job invoke")
        # This is a fatal, can't recover from it
        # let caller know 
        sys.exit(1)

    # First retry block: getting the job handle and printing parameters
    retries = default_retries
    while retries > 0:
        if retries < default_retries:
            print("Sleeping for 30 seconds")
            time.sleep(30)

        retries = retries - 1

        try:
            build = qi.get_job()
        except Exception as e:
            eprint(e)
            continue

        try:
            print_params(qi.get_parameters(), build)
            print('\nBuild:', build, "waiting to start...")

        except Exception as e:
            eprint(e)
            continue

        # Bust out of this retry loop
        retries = 0

    # Second retry loop: Blocks until build starts, streams console if needed
    retries = default_retries
    while retries > 0:
        if retries < default_retries:
            print("Sleeping for 30 seconds")
            time.sleep(30)

        retries = retries - 1

        try:
            build = qi.block_until_building()
            print(build, "started")

        except Exception as e:
            eprint(e)
            continue

        if stream:
            try:
                stream_console(build=build)
            except Exception as e:
                eprint(e)
                continue
        # if we made it here we're not in an exception, so leave
        retries = 0


def get_artifacts(job, number):
    """
        Look up the build number and get the artifacts
    """
    build = job.get_build(number)

    artifacts = build.get_artifacts()
    for art in artifacts:
        print(art.filename, art.url, art.build)
    return artifacts


def kill_job(job, number, stream=False):
    """
        Look up the build number and stop it.
            Stream option will let us watch the console log until the job ends
    """
    if not number:
        print("\nJob number not specified. Nothing to cancel.")
        return

    build = job.get_build(number)

    if build.is_running():
        print("Cancelling build", build)
        build.stop()
        if stream:
            stream_console(job=job, number=number)
        else:
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

def update_defaults(job=None, options=None):
    """
        Use some XML magic to update the job config
    """
    job_config_xml = job.get_config()
    jobconfig = xmltodict.parse(job_config_xml)

    # Grab a reference to the parameterDefinitions section of the job config.
    parameter_definitions = jobconfig['flow-definition']['properties']['hudson.model.ParametersDefinitionProperty']['parameterDefinitions']
    # Update the things that were specified
    for (key, value) in options.items():
        update_config(parameter_definitions, key, value)

    # This turns the dicts back into xml
    newconf = xmltodict.unparse(jobconfig, pretty=True)
    # Then update the job's config
    job.update_config(newconf)


def update_config(parameter_definitions=None, key=None, value=None):
    """
        Updates the specific parameter in the config xml
        Currently only handles bools or strings. Multivalue updates todo.
    """
    if type(value) is bool:
        config = parameter_definitions["hudson.model.BooleanParameterDefinition"]
    else:
        config = parameter_definitions["hudson.model.StringParameterDefinition"]

    # this will fail silently if the parameter doesn't exist.
    # TODO: Make this more informative to user
    for param in config:
        if param["name"] == key:
            param["defaultValue"] = value

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
    # Could have a parameter for a specific section, but whatever.
    sections = cfg.sections()
    sector = sections[0]
    uname = cfg[sector]['uname']
    token = cfg[sector]['token']
    server = cfg[sector]['server']

    return (server, uname, token)


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
            if '=' in parm:
                (key, value) = parm.split('=')
                # Fix up Bools if needed
                if value.lower() == "true":
                        value = True
                elif value.lower() == "false":
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
    parser = argparse.ArgumentParser(
        prog="janky.py",
        description="""Multi purpose Jenkins army knife""",
    )

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
                        help="Param changes in the form key=value,key2=value",
                        default=None)
    parser.add_argument("-s", "--stream", dest="stream_console",
                        action='store_true',
                        help="Stream the console for a job, or after build is launched",
                        default=False)
    parser.add_argument("-t", "--last", dest="last",
                        action='store_true',
                        help="Use last job as parameter source",
                        default=False)
    parser.add_argument("-u", "--update", dest="update_job",
                        action='store_true',
                        help="Update the job's default parameters with supplied params (Bool and String params only for now)",
                        default=False)
    parser.add_argument("-x", "--exec", dest="fire",
                        action='store_true',
                        help="Execute job with specified parameters",
                        default=False)

    options = parser.parse_args()

    # Parse the build parameter overrides into a dict
    if options.params:
        options.params = parse_params(options.params)

    if (options.stream_console or options.get_console) and not (options.last or options.build_number is not None):
       parser.error("Must specify a job (-n) or the most recent job (-t) in order to get or stream the console") 

    return options


def signal_handler(sig, frame):
    """
        Make aborts not barf all over the place
    """
    # print(sig, frame)
    if sig != signal.SIGINT:
        print(f'Wrong signal caught in {frame.f_code.co_name}, {frame.f_locals.keys()}')
    print('\nAborted.')
    sys.exit(0)


if __name__ == "__main__":
    main()
