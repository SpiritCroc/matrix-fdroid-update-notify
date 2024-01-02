#!/bin/bash

if [ -z "$formatted_msg" ]; then
    # Link to the upstream changelog
    echo "$msg" \
        | sed 's|\(Update codebase to \)\(Element X \)\(v.*\)|\1[\2\3](https://github.com/element-hq/element-x-android/blob/\3/CHANGES.md)|' \
        | sed 's|\(MSC \?\)\([1-9][0-9]*\)|[\1\2](https://github.com/matrix-org/matrix-spec-proposals/pull/\2)|'
else
    spoilered="$(echo "$formatted_msg" | sed 's|<p>\(.* updated SchildiChat Next to version <a .*'"$versionString"'</a>\.\)</p>|<details><summary>\1</summary>|')"
    if [ "$formatted_msg" != "$spoilered" ]; then
        # sed rule worked. Else, fallback to not inserting spoiler
        echo "$spoilered</details>"
    else
        echo "$formatted_msg"
    fi
fi
