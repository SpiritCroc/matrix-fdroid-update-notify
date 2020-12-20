#!/usr/bin/env python3

import asyncio
import inspect
import json
import os
import subprocess
import yaml

from markdown import markdown
from nio import AsyncClient

verbose = False
require_user_confirmation = False

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
def fp(repo_id, path):
    return os.path.expanduser(os.path.join(config['fdroid'][repo_id]['repo'], path))


def get_version_apk(repo_index, pkg, versionCode):
    for apk in repo_index['packages'][pkg]:
        if int(apk['versionCode']) == versionCode:
            return apk
    return None

def get_version_name(repo_index, pkg, versionCode):
    apk = get_version_apk(repo_index, pkg, versionCode)
    if apk != None:
        return apk['versionName']
    return None

def get_direct_download(repo_index, repo_id, pkg, versionCode):
    apk = get_version_apk(repo_index, pkg, versionCode)
    if apk != None and 'apkName' in apk:
        return config['fdroid'][repo_id]['repo_url'] + "/" + apk['apkName']
    return None

def last_notified_version(repo_id, pkg):
    try:
        with open(os.path.join(pkg_versions_dir, repo_id, pkg), "r") as fin:
            return int(fin.read())
    except:
        return None

def store_last_notified_version(repo_id, pkg, versionCode):
    store_dir = os.path.join(pkg_versions_dir, repo_id)
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
    with open(os.path.join(store_dir, pkg), "w") as fout:
        fout.write(str(versionCode))

async def bot_init():
    global client
    m_config = config["matrix"]
    client = AsyncClient(m_config["homeserver"], m_config["mx_id"], m_config["device_id"])
    await client.login(m_config["password"])
    await client.sync()

async def bot_finish():
    global client
    await client.logout()
    await client.close()

async def bot_update():
    for repo_id in config["fdroid"]:
        repo_config = config["fdroid"][repo_id]
        with open(fp(repo_id, "index-v1.json"), "r") as fin:
            repo_index = json.load(fin)

        for app in repo_index["apps"]:
            pkg = app["packageName"]
            name = app["name"]
            versionCode = int(app["suggestedVersionCode"])

            last_notified = last_notified_version(repo_id, pkg)
            if last_notified == None:
                print(f"{repo_id}/{pkg}: New app, remember version code {versionCode}")
                store_last_notified_version(repo_id, pkg, versionCode)
                continue
            if last_notified >= versionCode:
                if verbose:
                    print(f"{repo_id}/{pkg} does not require any notification")
                continue
            try:
                versionName = app["suggestedVersionName"]
            except:
                versionName = get_version_name(repo_index, pkg, versionCode)
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
            repo_name = config["fdroid"][repo_id]["repo_name"]
            repo_url = config["fdroid"][repo_id]["repo_url"]
            repoString = repo_name if repo_url == '' else f"[{repo_name}]({repo_url})"

            msg = f"{repoString} updated {name} to version {versionString}."
            if changes != None:
                msg += f"\n\nChanges:\n\n{changes}"

            if repo_id in config["update_message"]:
                if pkg in config["update_message"][repo_id]:
                    update_msg_config = config["update_message"][repo_id][pkg]
                    if "handler" in update_msg_config:
                        message_handler = update_msg_config["handler"]
                        env = os.environ.copy()
                        env["packageName"] = pkg
                        env["appName"] = name
                        env["versionString"] = versionString
                        env["repo_name"] = repo_name
                        env["repo_url"] = repo_url
                        env["repoString"] = repoString
                        env["msg"] = msg
                        env["changes"] = changes
                        msg = subprocess.check_output(message_handler, cwd=this_dir, env=env).decode('utf-8')

            store_last_notified_version(repo_id, pkg, versionCode)
            await notify_update(repo_id, pkg, msg)

async def post_notify(room, msg):
    if require_user_confirmation:
        input(f"Notify {room}: {msg}\nPress enter to confirm")
    elif verbose:
        print(f"Notify {room}: {msg}")
    else:
        print(f"Notify {room}")
    content = {
        "msgtype": "m.notice",
        "format": "org.matrix.custom.html",
        "body": msg,
        "formatted_body": markdown(msg)
    }
    await client.room_send(room, "m.room.message", content, ignore_unverified_devices=True)

async def notify_update(repo_id, pkg, msg):
    # "all" is a special "package" name to notify about all packages
    repo_rooms = config["matrix"]["rooms"][repo_id]
    for notify_id in ["all", pkg]:
        if notify_id in repo_rooms:
            for room in repo_rooms[notify_id]:
                await post_notify(room, msg)

async def main():
    await bot_init()
    await bot_update()
    await bot_finish()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
