#!/usr/bin/env python
from __future__ import print_function
import dxpy
import argparse
import sys
import os
import subprocess
import json
import time

dxWDL_version="0.60.2"
here = os.getcwd()
git_revision = subprocess.check_output(["git", "describe", "--always", "--dirty", "--tags"], cwd=here).strip()

def main():
    argparser = argparse.ArgumentParser(description="Build DVGLx workflow on DNAnexus.")
    argparser.add_argument("--project", help="DNAnexus project ID", default="project-FBQJgzQ04PyJ7JxZJJvZ39jX")
    argparser.add_argument("--folder", help="Folder within project (default: timestamp/git-based)", default=None)
    argparser.add_argument("--test", help="Build and run test workflow", action='store_true')
    argparser.add_argument("--no-wait", help="With --test, launch the analysis and exit without awaiting completion", action='store_true')
    args = argparser.parse_args()

    ensure_dxWDL()

    # set up environment
    if args.folder is None:
        args.folder = time.strftime("/builds/%Y-%m-%d/%H%M%S-") + git_revision

    project = dxpy.DXProject(args.project)
    print("project: {} ({})".format(project.name, args.project))
    project.new_folder(args.folder, parents=True)
    print("folder: {}".format(args.folder))

    # build the workflow
    wf = dxWDL("htsget_DeepVariant_GLnexus.wdl", project, args.folder)
    print("workflow: {} ({})".format(wf.name, wf.get_id()))

    # build and run the test, if desired
    if args.test:
        test_folder=args.folder+"/test"
        print("test folder: {}".format(test_folder))
        project.new_folder(test_folder)
        twf = dxWDL("test.wdl", project, test_folder, reorg=False, inputs="test.input.json")
        print("test workflow: {} ({})".format(twf.name, twf.get_id()))
        run_cmd=[
            "dx", "run", twf.get_id(),
            "--destination", "{}:{}".format(project.get_id(), test_folder),
            "--name", "DVGLx {} test".format(git_revision),
            "-f", "test.input.dx.json",
            "-y"
        ]
        if args.no_wait:
            subprocess.check_call(run_cmd)
        else:
            noise = subprocess.Popen(["/bin/bash", "-c", "while true; do sleep 60; date; done"])
            run_cmd = run_cmd + ["--wait"]
            try:
                subprocess.check_call(run_cmd)
                print("success")
            finally:
                noise.kill()

# download the dxWDL jar file if necessary
def ensure_dxWDL():
    dxWDL_fullname = "dxWDL-{}.jar".format(dxWDL_version)
    dxWDL_local_path = os.path.join(here, dxWDL_fullname)
    if not os.path.exists(dxWDL_local_path):
        # download the jar file
        download_cmd = [
            "wget", "-nv",
            "https://github.com/dnanexus-rnd/dxWDL/releases/download/{}/{}".format(dxWDL_version, dxWDL_fullname),
            "-O",
            dxWDL_local_path]
        print(" ".join(download_cmd))
        subprocess.check_call(download_cmd)
    return dxWDL_local_path

def dxWDL(filename, project, folder, reorg=True, inputs=None):
    dxWDL_path = ensure_dxWDL()
    cmd = ["java", "-jar", dxWDL_path, "compile",
           os.path.join(here, filename),
           "--project", project.get_id(),
           "--folder", folder]
    if inputs:
        cmd = cmd + ["--inputs", inputs]
    if reorg:
        cmd = cmd + ["--reorg"]

    buf = subprocess.check_output(cmd)
    wfid = buf.strip()
    wf = dxpy.DXWorkflow(wfid, project.get_id())
    wf.set_properties({"git_revision": git_revision})
    return wf

if __name__ == '__main__':
    main()

