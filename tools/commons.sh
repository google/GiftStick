#!/bin/bash
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This files contains a list of functions and variables to be used by other
# scripts in this directory.

readonly CURRENT_DIR=$(pwd)
readonly GIFT_USERNAME="gift"
readonly REMASTER_WORKDIR_NAME="remaster_workdir"
readonly REMASTER_WORKDIR_PATH=$(readlink -m "${CURRENT_DIR}/${REMASTER_WORKDIR_NAME}")
readonly REMASTER_SCRIPTS_DIR="${CODE_DIR}/remaster_scripts"
readonly FORENSICATE_SCRIPT_NAME="call_auto_forensicate.sh"
readonly FORENSICATE_SCRIPT_PATH="${REMASTER_SCRIPTS_DIR}/${FORENSICATE_SCRIPT_NAME}"
readonly AUTO_FORENSIC_SCRIPT_NAME="auto_acquire.py"

# Make sure the provided service account credentials file exists and is valid
function assert_sa_json_path {
  readonly local sa_json_path="${1}"
  if [[ ! -f "${sa_json_path}" ]] ; then
    die "${sa_json_path} does not exist"
  fi
  if ! grep -q '"type": "service_account",' "${sa_json_path}" ;  then
    die "${sa_json_path} does not look like a valid service account credentials JSON file"
  fi
}

# Prints an error and terminates execution.
#
# Arguments:
#  Message to display, as string.
function die {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

# Verifies a package has been installed with DPKG. Exits if package name is
# missing.
#
# Arguments:
#  Name of the package.
function check_packages {
  local pkg="$1"
  if ! dpkg --get-selections | grep -qE "^${pkg}[[:space:]]*install$"; then
    die "Please install package ${pkg}"
  fi
}

# Verifies that an option is not empty
#
# Arguments:
#  Option name, as string.
#  Option value, as string.
function assert_option_argument {
  if [[ -z $1 ]]; then
    die "$2 requires a non-empty option argument"
  fi
}
