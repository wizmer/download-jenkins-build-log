import requests
import argparse
import os
import shutil


def parse_command_line_arguments():
    """
    Parses the command-line arguments.
    :return: nothing
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("jobname", help="the name of the job")
    parser.add_argument("-u", "--url", help="the base URL of the Jenkins installation (default: http://localhost:8080)", default="http://localhost:8080")
    parser.add_argument("-b", "--build", help="the build ID (if omitted, the last build log will be downloaded)")
    parser.add_argument("-a", "--all", help="flag to indicate if all logs of the job should be downloaded", action="store_true")
    parser.add_argument("-d", "--directory", help="the target directory (defaults to '<job_name>-<build ID>')")
    args = parser.parse_args()

    global job_name
    global jenkins_url
    global build_id
    global download_all
    global target_directory

    job_name = args.jobname
    jenkins_url = args.url
    build_id = args.build
    download_all = args.all
    target_directory = args.directory if args.directory else "{}-{}".format(job_name, build_id if build_id else "last")


def get_last_build():
    """
    :return: the last build ID associate with the job
    """
    response = requests.get("{}/job/{}/api/json".format(jenkins_url, job_name))
    return response.json()['builds'][0]['number']


def create_target_directory():
    try:
        os.mkdir(target_directory)
    except FileExistsError:
        # ignore
        pass


def download_log_simple():
    response = requests.get("{}/job/{}/{}/consoleText".format(jenkins_url, job_name, build_id), stream=True)
    if response.status_code == 200:
        filename = "{}/{}".format(target_directory, build_id)
        with open(filename, 'wb') as f:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, f)
            print("Successfully downloaded log to " + filename)
        return 0
    else:
        print("Failed to download log, error code: {}, reason: {} ".format(
            response.status_code, response.reason))
        return -1


def download_log_matrix():
    response = requests.get("{}/job/{}/{}/api/json".format(jenkins_url, job_name, build_id))
    runs = response.json()['runs']
    for run in runs:
        run_url = run['url']
        response = requests.get("{}/consoleText".format(run_url), stream=True)
        if response.status_code == 200:
            # craft a file name that uses the matrix parameters
            filename = "{}/{}_{}".format(
                target_directory, build_id,
                run_url.split('/')[-3].replace('=', '_').replace(',', '_'))
            with open(filename, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
                print("Successfully downloaded log to " + filename)
        else:
            print("Failed to download log, error code: {}, reason: {} ".format(
                response.status_code, response.reason))
            return -1
    return 0


def download_logs():
    create_target_directory()

    global build_id
    if build_id is None:
        build_id = get_last_build()

    response = requests.get("{}/job/{}/{}/api/json".format(jenkins_url, job_name, build_id))
    job_class = response.json()['_class']
    if 'hudson.model.FreeStyleBuild' == job_class:
        return download_log_simple()
    elif 'org.jenkinsci.plugins.workflow.job.WorkflowRun' == job_class:
        return download_log_simple()
    elif 'hudson.matrix.MatrixBuild' == job_class:
        return download_log_matrix()

    return -1


parse_command_line_arguments()
result_code = download_logs()
exit(result_code)
