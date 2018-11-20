# -*- coding: utf-8 -*-
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

# This script builds a GiftStick image, runs it in qemu, starts the aquisition
# script from there, and checks the output image in GCS.

CLOUD_PROJECT=$1
GCS_BUCKET=$2
SA_CREDENTIALS_FILE=$3

ISO_TO_REMASTER_URL="http://mirror.us.leaseweb.net/ubuntu-cdimage/xubuntu/releases/18.04/release/xubuntu-18.04.1-desktop-amd64.iso"
ISO_FILENAME="xubuntu.iso"
IMAGE_NAME="giftstick.img"

REMASTER_SCRIPT="tools/remaster.sh"
CLOUD_PROJECT="plaso_ci"
GCS_PROJECT="giftstick-e2e"

set -e

# install required packages and things
function setup {
  sudo apt install -y \
    gdisk \
    genisoimage \
    grub2-common \
    grub-efi-amd64-bin \
    kpartx \
    squashfs-tools \
    syslinux
  download_iso "${ISO_TO_REMASTER_URL}" "${ISO_FILENAME}"
  return 0
}

# Downloads an ISO if not present
#
# Arguments:
#   The URL to download, as string
#   The destination filename, as string
function download_iso {
  readonly local url=$1
  readonly local filename=$2
  curl -z -J -O "${filename}" "${url}"
}

function build_image {
  bash "${REMASTER_SCRIPT}" \
    --project "${CLOUD_PROJECT}" \
    --bucket "${GCS_PROJECT}" \
    --skip_gcs \
    --source_iso "${ISO_FILENAME}" \
    --image "${IMAGE_NAME}" \
    --e2e_test \
    --sa_json_file "${SA_CREDENTIALS_FILE}"
}

function run_image {
  qemu-system-x86_64 -cpu qemu64 -bios /usr/share/ovmf/OVMF.fd  -m 1024 \
    -drive format=raw,file="${IMAGE_NAME}" -device e1000,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::5555-:22 -no-kvm -daemonize -display none
}

function run_acquisition_script {
  # Call python script from VM
  ssh  e2etest@localhost -p 5555 "cd /home/gift ; sudo bash /home/gift/call_auto_forensicate.sh"
}

function check_gcs {
  # Pull files from GCS and/or check their MD5
  return 0
}

function cleaup {
  kill -9 "$(pgrep qemu-system-x86_64)"
}

setup
build_image
run_acquisition_script
check_gcs
cleanup
