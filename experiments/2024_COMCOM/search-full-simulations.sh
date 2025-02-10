#!/usr/bin/env bash

set -eu

if [ $# -eq 0 ]; then
    echo "USAGE: $0 <CAPACITY>"
    echo "EXAMPLE: $0 0.0018"
    exit 1
fi

# source: https://stackoverflow.com/questions/29613304/is-it-possible-to-escape-regex-metacharacters-reliably-with-sed#29613573
# SYNOPSIS
#   quoteRe <text>
quoteRe() { sed -e 's/[^^]/[&]/g; s/\^/\\^/g; $!a\'$'\n''\\n' <<<"$1" | tr -d '\n'; }


CAPACITY="$1"
ESCAPED_CAPACITY=$(quoteRe "${CAPACITY}")

printf "These are the directories that have to be used instead of -FULL (CAPACITY=${CAPACITY}, escaped to ${ESCAPED_CAPACITY}):\n\n"
printf "SF: %s\n" $(rg --files-with-matches --glob "simulation_log.txt" -- "\/capacity-${ESCAPED_CAPACITY}.* --waterfall=1.*--reverse-waterfall=1.*--submarine-swaps=1" results/exp-1/SF_PCN/)
echo
printf "SH: %s\n" $(rg --files-with-matches --glob "simulation_log.txt" -- "\/capacity-${ESCAPED_CAPACITY}.* --waterfall=1.*--reverse-waterfall=1.*--submarine-swaps=1" results/exp-1/SH_PCN/)
printf "\nThis search algorithm is also implemented in utils.py:search_full_simulations\n"
