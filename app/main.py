from flask import Flask, request
import os
from google.cloud import storage
from packaging import version
import threading
app = Flask(__name__)

locking_dict = {}


@app.route("/go_ahead")
def check_status():
    appname = request.args.get('appname')
    schema_version = request.args.get('version')
    path_to_file = appname + "_check_version.pid"
    lock = get_lock_for_app(appname)
    lock.acquire()
    if os.path.exists(path_to_file):
        lock.release()
        return "wait"
    else:
        status = check_version_run_schema_change(schema_version, path_to_file)
        lock.release()
        return status


def get_lock_for_app(appname):
    if appname in locking_dict.keys():
        return locking_dict[appname]
    else:
        locking_dict[appname] = threading.Lock()
        return locking_dict[appname]


def check_version_run_schema_change(schema_version, path_to_file):
    create_pid_file(path_to_file)
    download_file_from_gcs()
    with open('running_version.txt', 'r') as file:
        running_version = file.read().replace('\n', '')

    if version.parse(running_version) < version.parse(schema_version):
        return "run"
    else:
        return "noneed"


def download_file_from_gcs():
    storage_client = storage.Client("dc-hughes-poc")
    bucket = storage_client.get_bucket("version_check_echostar_bucket")
    blob = bucket.blob("running_version.txt")
    blob.download_to_filename("running_version.txt")


def upload_file_to_gcs():
    storage_client = storage.Client("dc-hughes-poc")
    bucket = storage_client.get_bucket("version_check_echostar_bucket")
    blob = bucket.blob("running_version.txt")
    blob.upload_from_filename("running_version.txt")


def create_pid_file(path_to_file):
    with open(path_to_file, 'w') as fp:
        pass


def delete_pid_file(path_to_file):
    os.remove(path_to_file)


@app.route("/unlock_depl")
def unlock_depl():
    appname = request.args.get('appname')
    job_status = request.args.get('job_status')
    deploying_version = request.args.get('deploying_version')
    path_to_file = appname + "_check_version.pid"
    lock = get_lock_for_app(appname)
    lock.acquire()
    if job_status == "Success":
        with open('running_version.txt', "w") as file:
            file.write(deploying_version)
        upload_file_to_gcs()
        delete_pid_file(path_to_file)
    elif job_status == "Failed":
        delete_pid_file(path_to_file)
    elif job_status == "norun":
        delete_pid_file(path_to_file)
    lock.release()
    return "Done"


if __name__ == "__main__":
    app.run(host='0.0.0.0')
