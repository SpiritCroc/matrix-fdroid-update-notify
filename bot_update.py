#!/usr/bin/env python3

import asyncio
import inspect
import json
import os
import yaml

from markdown import markdown
from nio import AsyncClient

verbose=False

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


def get_version_apk(pkg, versionCode):
    for apk in repo_index['packages'][pkg]:
        if int(apk['versionCode']) == versionCode:
            return apk
    return None

def get_version_name(pkg, versionCode):
    apk = get_version_apk(pkg, versionCode)
    if apk != None:
        return apk['versionName']
    return None

def get_direct_download(pkg, versionCode):
    apk = get_version_apk(pkg, versionCode)
    if apk != None and 'apkName' in apk:
        return config['fdroid']['repo_url'] + "/" + apk['apkName']
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
            if verbose:
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
        repo_name = config["fdroid"]["repo_name"]
        repo_url = config["fdroid"]["repo_url"]

        msg = f"[{repo_name}]({repo_url}) updated {name} to version {versionString}."
        if changes != None:
            msg += f"\n\nChanges:\n\n{changes}"

        #download_url = get_direct_download(pkg, versionCode)
        #if download_url != None and False:
        #    # Disabled for now: direct download is discouraged, and looks wrong in this case
        #    msg += f"\n\nAvailable now from the [{repo_name}]({repo_url}) ([direct download]({download_url}))."
        #else:
        #    msg += f"\n\nAvailable now from the [{repo_name}]({repo_url})."

        store_last_notified_version(pkg, versionCode)
        await notify_update(pkg, msg)

async def post_notify(room, msg):
    input(f"Notify {room}: {msg}\nPress enter to confirm")
    content = {
        "msgtype": "m.notice",
        "format": "org.matrix.custom.html",
        "body": msg,
        "formatted_body": markdown(msg)
    }
    await client.room_send(room, "m.room.message", content, ignore_unverified_devices=True)

async def notify_update(pkg, msg):
    # "all" is a special "package" name to notify about all packages
    for notify_id in ["all", pkg]:
        if notify_id in config["matrix"]["rooms"]:
            for room in config["matrix"]["rooms"][notify_id]:
                await post_notify(room, msg)

async def main():
    await bot_init()
    await bot_update()
    await bot_finish()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
