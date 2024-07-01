# janky
Jenkins swiss army knife

#oh, one more thing
###stage-view.py
A pipeline stage viewer. Supposed to give you that job status page glance
from the terminal. Who wants to open a browser, clicky-clicky? Not me.

##Setup
First you're gonna need a Jenkins personal authorization token. Create one by
logging into your Jenkins account, clicking on your username in the top-right
corner, selecting "Configure", selecting "Add new Token" under the "API Tokens"
section, and following the prompts.

Then you're going to have to create a `janky.cfg` file with the following information:
```
[servernick]
uname: my_user_name
token: 123456JenkinsPersonalAccessToken
server: https://jenkins.jenkins.jk
```
So, put the url for your jenkins instance in the server field. Put the Jenkins
personal authorization token into the token field, and put your username in the
uname field. You are all set. QED.

## Runnnnnning it
### stage-view.py
```
usage: stage-view.py [-h] [-f FILENAME] [-j JOBNAME] [-l LIMIT]

Jenkins status from the shell.

options:
  -h, --help            show this help message and exit
  -f FILENAME, --filename FILENAME
                        Name of file to save pipeline json to
  -j JOBNAME, --jobname JOBNAME
                        Name of Jenkins job pipeline to view
  -l LIMIT, --limit LIMIT
                        Limit the number of lines
```

So, pretty easy. The filename is only for debugging. If something goes wrong
put that on and the results from the api call will be saved in the file.

Anyway, it's basically run stage-view and specify a job. I created the
jenkinslight class to make this faster. Regular Jenkins API tries to understand
everything about the server. job-view needs to get in and out fast.

#### Examples
Basic use:
`python3 job-view.py -j big-pipeline-job`
Only get one build's worth of info back:
`python3 job-view.py -j big-pipeline-job -l1`
Specify multiple jobs, but only return one build from each:
`python3 job-view.py -j big-pipeline-job,small-job,medium-job -l1`

### janky.py
This is the workhorse. Get build configuration information. Stream the console of a running build. Launch builds. Get the console (not streaming).
```
usage: janky.py [-h] [-c] [-j JOBNAME] [-k] [-n BUILD_NUMBER] [-l] [-p PARAMS] [-s] [-t] [-x]

Multi purpose Jenkins army knife

options:
  -h, --help            show this help message and exit
  -c, --console         Dump out the console text
  -j JOBNAME, --jobname JOBNAME
                        Name of Jenkins job to run
  -k, --kill            Kill build specified by -n
  -n BUILD_NUMBER, --number BUILD_NUMBER
                        Build number to kill or use parameters from
  -l, --list            List out parameters for specified build or job defaults
  -p PARAMS, --params PARAMS
                        Param changes in the form key=value,key2=value
  -s, --stream          Stream the console for a job, or after build is launched
  -t, --last            Use last job as parameter source
  -x, --exec            Execute job with specified parameters
```
