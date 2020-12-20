#!/bin/bash

# Link to the upstream changelog
echo "$msg" | sed 's|\(- Update codebase to \)\(Element \)\(v.*\)|\1[\2\3](https://raw.githubusercontent.com/vector-im/element-android/\3/CHANGES.md)|'
