#!/usr/bin/env bash

set -eu


CSV_FULLPATHS=( $(find . -type f -name "*.csv") )

for CSV_FULLPATH in "${CSV_FULLPATHS[@]}"; do
	CSV_FULLPATH=$(realpath "${CSV_FULLPATH}")
	DIRECTORY=$(dirname "${CSV_FULLPATH}")
	FILENAME=$(basename "${CSV_FULLPATH}")
	printf "DIR: %s, FNAME: %s, FULL_PATH: %s\n" "${DIRECTORY}" "${FILENAME}" "${CSV_FULLPATH}"
	pushd "${DIRECTORY}"
	gunzip "${FILENAME}"
	popd
done
