#!/usr/bin/env bash

set -eu

printf "These are the directories that have to be used instead of -FULL:\n\n"
printf "SF: %s\n" $(rg --files-with-matches --glob "simulation_log.txt" -- "--waterfall=1.*--reverse-waterfall=1.*--submarine-swaps=1" results/exp-1/SF_PCN/)
echo
printf "SH: %s\n" $(rg --files-with-matches --glob "simulation_log.txt" -- "--waterfall=1.*--reverse-waterfall=1.*--submarine-swaps=1" results/exp-1/SH_PCN/)
printf "\nThis search algorithm is also implemented in utils.py:search_full_simulations\n"
