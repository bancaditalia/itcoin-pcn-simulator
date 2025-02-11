#!/usr/bin/env bash

set -u
set -o errtrace
set -o pipefail
shopt -s inherit_errexit

errecho() {
    # prints to stderr
    >&2 echo "${@}"
}

log_info() {
    errecho "INFO: ${1}"
}

log_warning() {
    errecho "WARNING: ${1}"
}

log_error() {
    errecho "ERROR: ${1}"
}

errhandler() {
    # called when exiting
    if [[ $? -eq 0 ]]; then
        exit 0
    fi
    log_error "something went wrong at line: $(caller)"
    exit 1
}

trap errhandler ERR

# source: https://stackoverflow.com/questions/59895/how-do-i-get-the-directory-where-a-bash-script-is-located-from-within-the-script#246128
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

ARTIFACT_URL="https://zenodo.org/records/14848786/files/comcom25-experiment-results.tar"
ARTIFACT_FILE_NAME="comcom25-experiment-results.tar"
EXPECTED_SHA25SUM="f618ae26d241c2c59a159fa5d8810d2cb3ba327a55112b1f4378b987329db710"
RESULTS_DIR="${SCRIPT_DIR}/results"

USAGE=$(cat <<-END_HEREDOC
	USAGE:
	    ${0}

	This script will download the results of the experiments for the article
	"An Analysis of Pervasive Payment Channel Networks for Central Bank Digital Currencies"
	from the URL:
	    ${ARTIFACT_URL}
	and will put them in the directory:
	    ${SCRIPT_DIR}

	This is an alternative to executing all the experiments on your machine,
	which can be done invoking run_experiments.py.
END_HEREDOC
)

checkPrerequisites() {
    if ! command -v sha256sum &> /dev/null; then
        echo "Please install sha256sum"
        exit 1
    fi
    if ! command -v tar &> /dev/null; then
        echo "Please install tar (https://www.gnu.org/software/tar)"
        exit 1
    fi
    if ! command -v wget &> /dev/null; then
        echo "Please install wget (https://www.gnu.org/software/wget)"
        exit 1
    fi
}

promptInitialConfirmation() {
    local OK_TO_PROCEED
    OK_TO_PROCEED="INVALID"
    while true; do
        errecho
        read -p "Do you want to continue? [y/N] " -n 1 -r OK_TO_PROCEED
        echo
        if [[ "${OK_TO_PROCEED}" =~ ^[Yy]$ ]]; then
            return
        fi
        if [[ "${OK_TO_PROCEED}" =~ ^[Nn]$ ]] || [[ -z "${OK_TO_PROCEED}" ]]; then
            log_error "exiting on user request."
            exit 1
        fi
        [[ ! "${OK_TO_PROCEED}" =~ ^[YyNn]$ ]] || break
    done
}

ensureResultsAreEmpty() {
    local EXPERIMENT_DIRS
    local FULL_DIR
    local OK_TO_DELETE
    EXPERIMENT_DIRS=(
        exp-1
        exp-2
        exp-31
        exp-32
        exp-33
        exp-34
    )
    for DIR_NAME in "${EXPERIMENT_DIRS[@]}"; do
        FULL_DIR="${RESULTS_DIR}/${DIR_NAME}"
        OK_TO_DELETE="INVALID"
        if [ -d "${FULL_DIR}" ]; then
            errecho
            log_warning "${FULL_DIR} is not empty. In order to proceed you must delete it"
            while true; do
                read -p "Proceed to delete ${FULL_DIR}? [y/N] " -n 1 -r OK_TO_DELETE
                echo
                if [[ "${OK_TO_DELETE}" =~ ^[Yy]$ ]]; then
                    log_info "deleting ${FULL_DIR}"
                    rm -rf "${FULL_DIR}"
                fi
                if [[ "${OK_TO_DELETE}" =~ ^[Nn]$ ]] || [[ -z "${OK_TO_DELETE}" ]]; then
                    log_error "exiting on user request. Directory ${FULL_DIR} will NOT be deleted"
                    exit 1
                fi
                [[ ! "${OK_TO_DELETE}" =~ ^[YyNn]$ ]] || break
            done
        fi
    done
}

echo "${USAGE}"
promptInitialConfirmation

# Do not run if the required commands are not installed
log_info "Checking prerequisites"
checkPrerequisites


log_info "Ensuring the results directory does not contain previous results"
ensureResultsAreEmpty

log_info "Downloading experiment results from ${ARTIFACT_URL}"
wget --output-document="${SCRIPT_DIR}/${ARTIFACT_FILE_NAME}" --progress=none "${ARTIFACT_URL}"
log_info "Verifying sha256 sum"
echo "${EXPECTED_SHA25SUM}  ${ARTIFACT_FILE_NAME}" | sha256sum -c
log_info "Extracting"
tar xf "${ARTIFACT_FILE_NAME}" --directory="${RESULTS_DIR}" --strip-components=1
log_info "experiment results correctly downloaded, verified, and extracted to ${RESULTS_DIR}"
