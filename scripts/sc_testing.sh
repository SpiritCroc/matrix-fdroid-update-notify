#!/bin/bash

mydir="$(dirname "$(realpath "$0")")"

if [ "$packageName" = "de.spiritcroc.riotx.testing.fcm" ]; then
    # Escape brackets
    appNamePattern="$(echo "$appName" | sed 's;\(\[\|\]\);\\\1;g')"
    # Wrap it into spoiler (and convert to html to make it work)
    #echo -n "<details><summary>SchildiChat.Beta updated to version $versionString </summary>"
    if [ -z "$formatted_msg" ]; then
        "$mydir/de.spiritcroc.riotx.sh" | sed "s|$appNamePattern|SchildiChat.Beta|g" \
            | sed "s|^Changes:$|Auto-generated changelog:|"
    else
        spoilered="$(echo "$formatted_msg" | sed 's|<p>\(.* updated SchildiChat.Beta to version '"$versionString"'\.\)</p>|<details><summary>\1</summary>|')"
        if [ "$formatted_msg" != "$spoilered" ]; then
            # sed rule worked. Else, fallback to not inserting spoiler
            echo "$spoilered</details>"
        else
            echo "$formatted_msg"
        fi
    fi
elif [[ "$packageName" =~ "de.spiritcroc.riotx" ]]; then
    # Output nothing -> effectively blacklist updates for other variants
    :
else
    # Pass through proposed message
    echo "$msg"
fi
