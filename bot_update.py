#!/usr/bin/env python3

import argparse
import asyncio
import inspect
import json
import os
import subprocess
import yaml

from markdown import markdown
from nio import AsyncClient

parser = argparse.ArgumentParser(description="Send matrix notifications for your F-Droid repo updates")
parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
parser.add_argument("-c", "--require-confirmation", action="store_true", help="Ask for confirmation before sending updates")
parser.add_argument("--resend", action="store_true", help="Resend even if no version has been updated")
parser.add_argument("-r", "--redirect-room", metavar="roomId", type=str, help="Redirect all updates to a specific room. Will not remember the current updates, i.e. later invocations will notify again for updates.")
parser.add_argument("-p", "--package", metavar="packageId", type=str, help="Only check updates for a specific app with the given package ID.")
args = parser.parse_args()

verbose = args.verbose
require_user_confirmation = args.require_confirmation
should_resend = args.resend
redirect_room = args.redirect_room
restrict_package = args.package
should_store = redirect_room == None

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
    if not should_store:
        return
    store_dir = os.path.join(pkg_versions_dir, repo_id)
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
    with open(os.path.join(store_dir, pkg), "w") as fout:
        fout.write(str(versionCode))

async def bot_init():
    global client
    if verbose:
        print("Login matrix bot...")
    m_config = config["matrix"]
    client = AsyncClient(m_config["homeserver"], m_config["mx_id"], m_config["device_id"])
    await client.login(m_config["password"])
    if verbose:
        print("Sync matrix bot...")
    await client.sync()
    if verbose:
        print("Matrix bot ready!")

async def bot_finish():
    global client
    await client.logout()
    await client.close()

async def bot_update():
    for repo_id in config["fdroid"]:
        repo_config = config["fdroid"][repo_id]
        if verbose:
            print("Loading repo index...")
        with open(fp(repo_id, "index-v1.json"), "r") as fin:
            repo_index = json.load(fin)
        if verbose:
            print("Repo index loaded!")

        for app in repo_index["apps"]:
            #print(json.dumps(app, indent=4))
            pkg = app["packageName"]
            if restrict_package not in [pkg, None]:
                continue
            try:
                name = app["name"]
            except KeyError:
                name = app["localized"]["en-US"]["name"]
            versionCode = int(app["suggestedVersionCode"])
            if not os.path.exists(fp(repo_id, f"../repo/{pkg}_{versionCode}.apk")):
                print(f"ERROR: Suggested version {versionCode} does not exist for {pkg}, skipping this app")
                continue

            last_notified = last_notified_version(repo_id, pkg)
            if last_notified == None and not should_resend:
                print(f"{repo_id}/{pkg}: New app, remember version code {versionCode}")
                store_last_notified_version(repo_id, pkg, versionCode)
                continue
            if last_notified >= versionCode and not should_resend:
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
                try:
                    with open(fp(repo_id, f"../build/{pkg}/fastlane/metadata/android/en-US/changelogs/{versionCode}.txt"), "r") as fin:
                        changes = fin.read()
                    print(f"{repo_id}/{pkg}: found fastlane changelog")
                except:
                    changes = app["localized"]["en-US"]["whatsNew"]
                    print(f"{repo_id}/{pkg}: use fdroid changelog")
            except:
                changes = None
            if changes != None and changes[-1] == '\n':
                changes = changes[:-1]
            versionString = f"{versionName}" if versionName != None else f"{versionCode}"
            unformattedVersionString = versionString
            repo_name = config["fdroid"][repo_id]["repo_name"]
            repo_url = config["fdroid"][repo_id]["repo_url"]
            repoString = repo_name if repo_url == '' else f"[{repo_name}]({repo_url})"

            try:
                source_url = app["sourceCode"]
                if source_url.startswith("https://github.com") and source_url.count("/") == 4:
                    # Try to get the actual tag / commit that this was built against from metadata.
                    with open(fp(repo_id, os.path.join("..", "metadata", f"{pkg}.yml")), "r") as fin:
                        metadata = yaml.full_load(fin)
                        builds = metadata["Builds"]
                        for build in builds:
                            print(f"{build['versionCode']} == {versionCode}")
                            if build['versionCode'] == versionCode:
                                revision = build["commit"]
                                versionString = f"[{versionString}]({source_url}/commits/{revision})"
                                break
            except Exception as e:
                print(f"Can not parse metadata for {pkg} to find git revision")

            msg = f"{repoString} updated {name} to version {versionString}."
            if changes != None:
                # Changelog should not generate an @room-ping
                changes = changes.replace("@room", "@\u2060room")
                msg += f"\n\nChanges:\n\n{changes}"

            formatted_msg = markdown(msg)

            if repo_id in config["update_message"]:
                for notify_id in [pkg, "all"]:
                    if notify_id in config["update_message"][repo_id]:
                        update_msg_config = config["update_message"][repo_id][notify_id]
                        if "handler" in update_msg_config:
                            message_handler = update_msg_config["handler"]
                            print(f"Run message handler {message_handler} for {pkg}")
                            env = os.environ.copy()
                            env["packageName"] = pkg
                            env["appName"] = name
                            env["versionString"] = unformattedVersionString
                            env["repo_name"] = repo_name
                            env["repo_url"] = repo_url
                            env["repoString"] = repoString
                            env["msg"] = msg
                            env["formatted_msg"] = ""
                            if changes != None:
                                env["changes"] = changes
                            elif "changes" in env:
                                del env["changes"]
                            # Run once without formatted_msg empty to generate unformatted message
                            msg = subprocess.check_output(message_handler, cwd=this_dir, env=env).decode('utf-8')
                            formatted_msg = markdown(msg)

                            # Rerun for formatted msg. Scripts that want to modify the formatted message further
                            # should check if formatted_msg is empty in order to tell apart executions for formatted
                            # and plain messages.
                            env["formatted_msg"] = formatted_msg
                            formatted_msg = subprocess.check_output(message_handler, cwd=this_dir, env=env).decode('utf-8')
                            # If formatted_msg = msg, then the script does likely not check for formatted_msg,
                            # and just always handle msg. In this case, we want to re-format the message.
                            if formatted_msg == msg:
                                formatted_msg = markdown(msg)

            store_last_notified_version(repo_id, pkg, versionCode)
            if len(msg) > 1:
                await notify_update(repo_id, pkg, msg, formatted_msg)
            else:
                # Discard messages
                print(f"Don't notify for {repo_id} / {pkg} / {versionCode}")

async def post_notify(room, msg, formatted_msg, notice):
    if redirect_room != None:
        room = redirect_room
    if require_user_confirmation:
        input(f"Notify {room}: {msg}\nPress enter to confirm")
    elif verbose:
        print(f"Notify {room}: {msg}")
    else:
        print(f"Notify {room}")
    content = {
        "msgtype": "m.notice" if notice else "m.text",
        "format": "org.matrix.custom.html",
        "body": msg,
        "formatted_body": formatted_msg
    }
    await client.room_send(room, "m.room.message", content, ignore_unverified_devices=True)

async def notify_update(repo_id, pkg, msg, formatted_msg):
    for notice_enabled, notice_id in [(True, "notice"), (False, "text")]:
        repo_rooms = config["matrix"]["rooms"][repo_id]
        if not notice_id in repo_rooms:
            continue
        repo_rooms = repo_rooms[notice_id]
        # "all" is a special "package" name to notify about all packages
        for notify_id in ["all", pkg]:
            if notify_id in repo_rooms:
                for room in repo_rooms[notify_id]:
                    await post_notify(room, msg, formatted_msg, notice_enabled)

async def main():
    await bot_init()
    await bot_update()
    await bot_finish()

if __name__ == "__main__":
    asyncio.new_event_loop().run_until_complete(main())
