import requests
import argparse
import os
import shutil
import attr
import click
from pathlib import Path


@attr.s
class Config:
    job_name = attr.ib()
    jenkins_url = attr.ib()
    build_id = attr.ib()
    download_all = attr.ib()
    target_directory = attr.ib()
    login_name = attr.ib()
    api_token = attr.ib()

    @property
    def job_url(self):
        return f"{self.jenkins_url}/job/{self.job_name}/{self.build_id}"


def get(url, config, **kwargs):
    return requests.get(url, auth=(config.login_name, config.api_token), **kwargs)

def get_last_build(config):
    """
    :return: the last build ID associate with the job
    """
    response = get(f"{config.jenkins_url}/job/{config.job_name}/api/json", config)
    if response.status_code != 200:
        raise Exception("Unexpected error received from server: status code={} reason={}".format(
            response.status_code, response.reason))
    return response.json()['builds'][0]['number']


def download_log_simple(config):
    """
    Download the log of job types that have a single console log
    :return: 0 in case of success, -1 in case of an error
    """
    response = get(f"{config.job_url}/consoleText", config, stream=True)
    if response.status_code == 200:
        filename = f"{config.target_directory}/{config.build_id}"
        with open(filename, 'wb') as f:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, f)
            print("Successfully downloaded log to " + filename)
        return 0
    else:
        print("Failed to download log, error code: {}, reason: {} ".format(
            response.status_code, response.reason))
        return -1


def download_log_matrix(config):
    """
    Download the logs of jobs with multiple console log files
    :return: 0 in case of success, -1 in case of an error
    """
    response = get(f"{config.job_url}/api/json", config)
    if response.status_code != 200:
        raise Exception("Unexpected error received from server: status code={} reason={}".format(
            response.status_code, response.reason))

    runs = response.json()['runs']


    for run in filter(lambda run: 'TOXENV=py36,platform=bb5' in run['url'], runs):
        run_url = run['url']
        response = get(f"{run_url}/consoleText", config, stream=True)
        if response.status_code == 200:
            url_str = run_url.split('/')[-3].replace('=', '_').replace(',', '_')
            filename = f"{config.target_directory}/{config.build_id}_{url_str}"
            with open(filename, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
                return filename
        else:
            print("Failed to download log, error code: {}, reason: {} ".format(
                response.status_code, response.reason))
            return -1
    return 0


def download_logs(config):
    """
    Download the build log file(s) to the destination directory
    :return: 0 in case of success, -1 in case of an error
    """
    response = get(f"{config.job_url}/api/json", config)
    if response.status_code != 200:
        raise Exception("Unexpected error received from server: status code={} reason={}".format(
            response.status_code, response.reason))

    job_class = response.json()['_class']
    if 'hudson.model.FreeStyleBuild' == job_class:
        return download_log_simple(config)
    elif 'org.jenkinsci.plugins.workflow.job.WorkflowRun' == job_class:
        return download_log_simple(config)
    elif 'hudson.matrix.MatrixBuild' == job_class:
        return download_log_matrix(config)

    return -1


@click.command(help='Download Jenkins logs')
@click.argument("jobname")
@click.option("-u", "--url",
              help="the base URL of the Jenkins installation (default: http://localhost:8080)",
              default="https://bbpcode.epfl.ch/ci/")
@click.option("-b", "--build",
              help="the build ID (if omitted, the last build log will be downloaded)")
@click.option("-a", "--all/--no-all",
              help="flag to indicate if all logs of the job should be downloaded", default=True)
@click.option("-d", "--directory",
              help="the target directory (defaults to '<job_name>-<build ID>')")
@click.option("-l", "--login", help="the login name to the Jenkins server")
@click.option("-p", "--token", help="the API token to the Jenkins server")
def main(jobname, url, build, all, directory, login, token):
    directory = directory or "{}-{}".format(jobname, build if build else "last")
    login_name = login or os.environ.get('DOWNLOAD_JENKINS_BUILD_LOG_LOGIN')
    api_token = token or os.environ.get('DOWNLOAD_JENKINS_BUILD_LOG_API_TOKEN')

    config = Config(job_name=jobname,
                    jenkins_url = url,
                    build_id = build,
                    download_all = all,
                    target_directory = directory,
                    login_name = login_name,
                    api_token = api_token)

    if config.build_id is None:
        config.build_id = get_last_build(config)

    Path(config.target_directory).mkdir(parents=True, exist_ok=True)

    filename = download_logs(config)

    with open(filename) as f:
        for line in filter(None, map(lambda line: line.strip(), f)):
            print(line)
