#!/usr/bin/env python3

import inspect
import json
import os
import yaml

# Directory containing this file
this_dir = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]))

# relative path
def rp(path):
    return os.path.join(this_dir, path)

work_dir = rp(".data")
if not os.path.exists(work_dir):
    os.makedirs(work_dir)

# workdir path
def wp(path):
    return os.path.join(work_dir, path)

pkg_versions_dir = wp("pkg_versions")
if not os.path.exists(pkg_versions_dir):
    os.makedirs(pkg_versions_dir)

with open(rp('bot.yaml')) as fin:
    config = yaml.full_load(fin)


# fdroid repo path
def fp(path):
    return os.path.expanduser(os.path.join(config['fdroid']['repo'], path))

with open(fp("index-v1.json"), "r") as fin:
    repo_index = json.load(fin)


def get_version_name(pkg, versionCode):
    for apk in repo_index['packages'][pkg]:
        if int(apk['versionCode']) == versionCode:
            return apk['versionName']
    return None

def last_notified_version(pkg):
    try:
        with open(os.path.join(pkg_versions_dir, pkg), "r") as fin:
            return int(fin.read())
    except:
        return None

def store_last_notified_version(pkg, versionCode):
    with open(os.path.join(pkg_versions_dir, pkg), "w") as fout:
        fout.write(str(versionCode))

def bot_update():
    for app in repo_index["apps"]:
        pkg = app["packageName"]
        name = app["name"]
        versionCode = int(app["suggestedVersionCode"])

        last_notified = last_notified_version(pkg)
        if last_notified == None:
            print(f"Never notified for {pkg}, remembering version code {versionCode}")
            store_last_notified_version(pkg, versionCode)
            continue
        if last_notified >= versionCode:
            print(f"{pkg} does not require any notification")
            continue
        try:
            versionName = app["suggestedVersionName"]
        except:
            versionName = get_version_name(pkg, versionCode)
        if versionName == None:
            print(f"WARN: No version name found for {pkg}, {versionCode}")
            continue
        try:
            changes = app["localized"]["en-US"]["whatsNew"]
            if changes[-1] == '\n':
                changes = changes[:-1]
        except:
            changes = None
        versionString = f"{versionName}" if versionName != None else f"{versionCode}"
        changesString = f"\n{changes}" if changes != None else ""
        msg = f"{name} updated to {versionString}{changesString}"

        store_last_notified_version(pkg, versionCode)
        notify_update(pkg, msg)

def post_notify(room, msg):
    pass
    print(f"Notify {room}: {msg}")

def notify_update(pkg, msg):
    # "all" is a special "package" name to notify about all packages
    for notify_id in ["all", pkg]:
        if notify_id in config["matrix"]["rooms"]:
            for room in config["matrix"]["rooms"][notify_id]:
                post_notify(room, msg)

if __name__ == "__main__":
    bot_update()
