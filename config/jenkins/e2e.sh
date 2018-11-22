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

CLOUD_PROJECT=""
GCS_BUCKET=""
SA_CREDENTIALS_FILE=""

ISO_TO_REMASTER_URL="http://mirror.us.leaseweb.net/ubuntu-cdimage/xubuntu/releases/18.04/release/xubuntu-18.04.1-desktop-amd64.iso"
ISO_FILENAME=${ISO_TO_REMASTER_URL##*/}
IMAGE_NAME="giftstick.img"

REMASTER_SCRIPT="tools/remaster.sh"

set -e

# install required packages and things
function setup {
  sudo apt update -y
  sudo apt install -y \
    gdisk \
    genisoimage \
    grub2-common \
    grub-efi-amd64-bin \
    kpartx \
    ovmf \
    qemu-system-x86 \
    squashfs-tools \
    syslinux \
    syslinux-utils \
    wget

  if [ ! -f "${ISO_FILENAME}" ]; then
    wget -nc -O "${ISO_FILENAME}" "${ISO_TO_REMASTER_URL}"
  fi
}

function build_image {
  bash "${REMASTER_SCRIPT}" \
    --project "${CLOUD_PROJECT}" \
    --bucket "${GCS_BUCKET}" \
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
  echo "Waiting for qemu to finish booting..."
  sleep $((4*60))
}

function run_acquisition_script {
  cat >test_key <<EOKEY
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACB8dujxMxI+ViGQz/wHLa+C67gIiBW1T+IUvADQa3J5xwAAALDY6JAB2OiQ
AQAAAAtzc2gtZWQyNTUxOQAAACB8dujxMxI+ViGQz/wHLa+C67gIiBW1T+IUvADQa3J5xw
AAAECGsXl/bYnTqdXNZCxXI3ZcjmnCRODj2yGyqjTF1T62Ynx26PEzEj5WIZDP/Actr4Lr
uAiIFbVP4hS8ANBrcnnHAAAAJnJvbWFpbmdAZ3JpbWJlcmdlbi56cmguY29ycC5nb29nbG
UuY29tAQIDBAUGBw==
-----END OPENSSH PRIVATE KEY-----
EOKEY
  chmod 600 test_key
  ssh -v \
    -oIdentityFile=test_key \
    -oUserKnownHostsFile=/dev/null \
    -oStrictHostKeyChecking=no gift@localhost \
    -p 5555 \
    "cd /home/gift ; sudo bash /home/gift/call_auto_forensicate.sh"
}

function check_gcs {
  # Pull files from GCS and/or check their MD5
  return 0
}

function cleaup {
  kill -9 "$(pgrep qemu-system-x86_64)"
}

function main {
  CLOUD_PROJECT=$1
  GCS_BUCKET=$2
  SA_CREDENTIALS_FILE=$3

  echo "Setting up environment"
  setup
  echo "Starting GiftStick image building process"
  build_image
  echo "Starting up GiftStick image"
  run_image
  echo "Starting up acquisition scripts"
  run_acquisition_script
  echo "Checking files are up in GCS"
  check_gcs
  echo "Cleaning up"
  cleanup
  echo "Done"
}

trap "{
  exit 1
}" INT EXIT

main "$@"
