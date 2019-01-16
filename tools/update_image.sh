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

set -e

readonly CODE_DIR=$(realpath "$(dirname "$0")")
# shellcheck source=commons.sh
. "${CODE_DIR}/commons.sh"


FLAGS_NEW_GCS_REMOTE_URL=""
FLAGS_NEW_SA_CREDENTIALS_FILE=""
FLAGS_SOURCE_IMAGE=""

# Hardcoded values
readonly PARTITION_MOUNTPOINT="${REMASTER_WORKDIR_PATH}/root"
readonly GIFT_HOMEDIR="${PARTITION_MOUNTPOINT}/upper/home/${GIFT_USERNAME}/"

# Some Global variable
LOSETUP_DEVICE=""
NEW_SA_CREDENTIALS_PATH=""
NEW_SA_CREDENTIALS_FILENAME=""

# Displays the help message
function show_usage {
  echo "
Usage: update_image.sh [OPTIONS]
Updates a GiftStick image generated with tools/remaster.sh.

Example use:

  bash update_image.sh --source_image giftstick-20190101.img --sa_json_file service_account.json

Mandatory flags:
  --source_image=IMAGE  The GiftStick image to update.

Optional flags
  -h, --help            Show this help message
  --gcs_remote_url      Set a new GCS remote URL.
  --sa_json_file        Use this Service Account credentials file to connect to
                        GCS."
}

# Make sure that FLAGS_SOURCE_IMAGE is defined
function assert_source_image_flag {
  if [[ ! "${FLAGS_SOURCE_IMAGE}" ]]; then
    die "Please specify a source GiftStick image to update with --source_image"
  fi
  if [[ ! -f "${FLAGS_SOURCE_IMAGE}" ]]; then
    die "${FLAGS_SOURCE_IMAGE} is not found"
  fi
  FLAGS_SOURCE_IMAGE=$(readlink -m "${FLAGS_SOURCE_IMAGE}")
}

# Parses the command line arguments
#
# Arguments:
#  The list of command line arguments separated by spaces, as string.
function parse_arguments {
  while :; do
    case $1 in
      -h|--help)
        show_usage
        exit
        ;;

      --source_image)
        assert_option_argument "$2" "--source_image"
        FLAGS_SOURCE_IMAGE="$2"
        shift
        ;;
      --source_image=?*)
        FLAGS_SOURCE_IMAGE=${1#*=}
        ;;
      --source_image=)
        die '--source_image requires a non-empty option argument.'
        ;;

      --gcs_remote_url)
        assert_option_argument "$2" "--gcs_remote_url"
        FLAGS_NEW_GCS_REMOTE_URL="$2"
        shift
        ;;
      --gcs_remote_url=?*)
        FLAGS_NEW_GCS_REMOTE_URL=${1#*=}
        ;;
      --gcs_remote_url=)
        die '--gcs_remote_url requires a non-empty option argument.'
        ;;


      --sa_json_file)
        assert_option_argument "$2" "--sa_json_file"
        FLAGS_NEW_SA_CREDENTIALS_FILE="$2"
        shift
        ;;
      --sa_json_file=?*)
        FLAGS_NEW_SA_CREDENTIALS_FILE=${1#*=}
        ;;
      --sa_json_file=)
        die '--sa_json_file requires a non-empty option argument.'
        ;;

      *)
        if [[ "$1" == "" ]]; then
          break
        else
          die "unknown option '$1'."
        fi
    esac
    shift
  done

  assert_source_image_flag
  if [[ ! -z "${FLAGS_NEW_SA_CREDENTIALS_FILE}" ]] ; then
    check_packages "jq"
    assert_sa_json_path "${FLAGS_NEW_SA_CREDENTIALS_FILE}"
    NEW_SA_CREDENTIALS_PATH=$(readlink -m "${FLAGS_NEW_SA_CREDENTIALS_FILE}")
    NEW_SA_CREDENTIALS_FILENAME=$(basename "${NEW_SA_CREDENTIALS_PATH}")
  fi

  if [[ ! -z "${FLAGS_NEW_GCS_REMOTE_URL}" ]] ; then
    assert_gcs_url "${FLAGS_NEW_GCS_REMOTE_URL}"
  fi

}

function update_sa_credentials {
  pushd "${GIFT_HOMEDIR}" > /dev/null
  sudo cp "${NEW_SA_CREDENTIALS_PATH}" "${NEW_SA_CREDENTIALS_FILENAME}"
  sudo sed -i "s/GCS_SA_KEY_FILE=.*\$/GCS_SA_KEY_FILE=\"${NEW_SA_CREDENTIALS_FILENAME}\"/" "${CONFIG_FILENAME}"
  popd > /dev/null
}

function update_gcs_remote_url {
  pushd "${GIFT_HOMEDIR}" > /dev/null
  # Need to escape all / in FLAGS_NEW_GCS_REMOTE_URL
  sudo sed -i "s/GCS_REMOTE_URL=.*\$/GCS_REMOTE_URL=\"${FLAGS_NEW_GCS_REMOTE_URL//\//\\\/}\"/" "${CONFIG_FILENAME}"
  popd > /dev/null
}

function mount_partition {
  LOSETUP_DEVICE=$(sudo losetup -fP --show "${FLAGS_SOURCE_IMAGE}")
  mkdir -p "${PARTITION_MOUNTPOINT}"
  sudo mount "${LOSETUP_DEVICE}p2" "${PARTITION_MOUNTPOINT}"
}

function main {
  # Create working directory if needed.
  mkdir -p "${REMASTER_WORKDIR_PATH}"

  parse_arguments "$@"


  mount_partition

  if [[ ! -f "${GIFT_HOMEDIR}/config.sh" ]] ; then
    echo "Couldn't find config file ${GIFT_HOMEDIR}/config.sh"
    die "Are you sure this is a GiftStick image?"
  fi

  if [[ ! -z "${FLAGS_NEW_SA_CREDENTIALS_FILE}" ]] ; then
    update_sa_credentials
  fi

  if [[ ! -z "${FLAGS_NEW_GCS_REMOTE_URL}" ]] ; then
    update_gcs_remote_url
  fi
}

# This trap restores a clean environment. In case of failure, we won't have
# leftovers mounted filesystems.
function trap_cleanup {
  if [[ -d "${CURRENT_DIR}" ]]; then
    cd "${CURRENT_DIR}"
    mountpoint -q "${PARTITION_MOUNTPOINT}" && sudo -n umount "${PARTITION_MOUNTPOINT}"
    loop_devices=$(losetup -O NAME --noheadings -j "${FLAGS_SOURCE_IMAGE}")
    for loop_device in ${loop_devices}; do
      sudo losetup -d "${loop_device}"
    done
    if [[ -d "${PARTITION_MOUNTPOINT}" ]] ; then
      rmdir "${PARTITION_MOUNTPOINT}"
    fi
    if [[ -d "${REMASTER_WORKDIR_PATH}" ]] ; then
      rmdir "${REMASTER_WORKDIR_PATH}"
    fi
  fi
}


trap "{
  trap_cleanup
}" INT EXIT


main "$@"
