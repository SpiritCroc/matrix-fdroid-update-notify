#!/bin/bash

mydir="$(dirname "$(realpath "$0")")"

"$mydir/de.spiritcroc.riotx.sh" | sed "s|$appName|SchildiChat beta|"
