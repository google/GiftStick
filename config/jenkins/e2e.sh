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

readonly GIFT_USER="gift"
readonly ISO_TO_REMASTER_URL="http://mirror.us.leaseweb.net/ubuntu-cdimage/xubuntu/releases/18.04/release/xubuntu-18.04.1-desktop-amd64.iso"
readonly ISO_FILENAME=${ISO_TO_REMASTER_URL##*/}
readonly IMAGE_NAME="giftstick.img"

readonly REMASTER_SCRIPT="tools/remaster.sh"
readonly SSH_KEY_PATH="test_key"
readonly QEMU_SSH_PORT=5555

set -e

function msg {
  local message=$1
  echo "[$(date +%Y%m%d-%H%M%S)] ${message}"
}

# install required packages and things
function setup {
  sudo apt update -y
  sudo apt install -y \
    gdisk \
    genisoimage \
    kpartx \
    ovmf \
    qemu-system-x86 \
    squashfs-tools \
    syslinux \
    syslinux-utils \
    wget

   # Xenial version of grub-efi-amd64-bin: 2.02~beta2-36ubuntu3 doesn't
   # generate bootable images, for an unknown reason.
   # Since our current CI environment uses Xenial, let's for installation
   # of 2.02-2ubuntu8 from bionic hosted on GCE
   add-apt-repository 'deb http://europe-west1.gce.archive.ubuntu.com/ubuntu/ bionic main'
   cat >/etc/apt/preferences.d/limit-bionic <<EOAPT
Package: *
Pin: release o=Ubuntu,a=bionic
Pin-Priority: 150
EOAPT

  apt update -y
  apt install -y grub-common=2.02-2ubuntu8
  apt install -y grub-efi-amd64-bin=2.02-2ubuntu8

  if [ ! -f "${ISO_FILENAME}" ]; then
    wget -q -nc -O "${ISO_FILENAME}" "${ISO_TO_REMASTER_URL}"
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

function ssh_and_run {
  local ssh_command=$1
  if [ ! -f "${SSH_KEY_PATH}" ]; then
    # The corresponding public key is pushed in the giftstick "e2etest" image.
    # The image is running in Qemu, in the VM that is running the Jenkins Job.
    cat >"${SSH_KEY_PATH}" <<EOKEY
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACB8dujxMxI+ViGQz/wHLa+C67gIiBW1T+IUvADQa3J5xwAAALDY6JAB2OiQ
AQAAAAtzc2gtZWQyNTUxOQAAACB8dujxMxI+ViGQz/wHLa+C67gIiBW1T+IUvADQa3J5xw
AAAECGsXl/bYnTqdXNZCxXI3ZcjmnCRODj2yGyqjTF1T62Ynx26PEzEj5WIZDP/Actr4Lr
uAiIFbVP4hS8ANBrcnnHAAAAJnJvbWFpbmdAZ3JpbWJlcmdlbi56cmguY29ycC5nb29nbG
UuY29tAQIDBAUGBw==
-----END OPENSSH PRIVATE KEY-----
EOKEY
    chmod 600 "${SSH_KEY_PATH}"
  fi
  echo Running ssh  \
    -oIdentityFile=${SSH_KEY_PATH} \
    -oUserKnownHostsFile=/dev/null \
    -oStrictHostKeyChecking=no \
    -oConnectTimeout=5 \
    -p "${QEMU_SSH_PORT}" \
    "${GIFT_USER}@localhost" \
    "${ssh_command}"
  ssh  \
    -oIdentityFile=${SSH_KEY_PATH} \
    -oUserKnownHostsFile=/dev/null \
    -oStrictHostKeyChecking=no \
    -oConnectTimeout=5 \
    -p "${QEMU_SSH_PORT}" \
    "${GIFT_USER}@localhost" \
    "${ssh_command}"
}

function run_image {
  qemu-system-x86_64 -cpu qemu64 -bios /usr/share/ovmf/OVMF.fd  -m 1024 \
    -drive format=raw,file="${IMAGE_NAME}" -device e1000,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::${QEMU_SSH_PORT}-:22 -no-kvm -daemonize -display none

  # Cloud VMs lack any kind of virtualization super powers, so booting a
  # Ubuntu VM in a vm can take around forever.
  msg "Waiting 10 mins for qemu to settle"
  sleep $((10*60))
  local tries=10
  for try in $(seq 1 $tries); do
    if ssh_and_run "echo 'logged in'"; then
      break
    fi
    msg "Waiting 10 more seconds for qemu to settle ${try}/${tries}"
    sleep 10
  done
}

function run_acquisition_script {
  ssh_and_run "cd /home/gift ; sudo bash /home/gift/call_auto_forensicate.sh"
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

  msg "Setting up environment"
  setup
  msg "Starting GiftStick image building process"
  build_image
  msg "Starting up GiftStick image"
  run_image
  msg "Starting up acquisition scripts"
  run_acquisition_script
  msg "Checking files are up in GCS"
  check_gcs
  msg "Cleaning up"
  cleanup
  msg "Done"
}

trap "{
  exit 1
}" INT EXIT

main "$@"
