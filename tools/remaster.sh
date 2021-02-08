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
#
#
# This script can be used to generate a usb disk image containing Forensic
# tools used by the security team.
#
# Example use:
# $ bash remaster.sh --source_iso "xubuntu-18.04-desktop-amd64.iso"
# --project mycloudproject --bucket bucket-name
#
# You should end up with a file called gift-image-$(date +%Y%m%d).img, unless
# you specify the destination with --image
#
# It requires the following packages, on ubuntu:
#   gdisk genisoimage grub-efi-amd64-bin syslinux syslinux-utils
#   initramfs-tools-core
#
# gdisk and grub-efi-amd64-bin are used for the EFI booting part.
#
# If you want to try the new USB image in Qemu, install the following packages:
#   qemu-system-x86 and ovmf

set -e

readonly CODE_DIR=$(realpath "$(dirname "$0")")
# shellcheck source=commons.sh
. "${CODE_DIR}/commons.sh"

# Default values
readonly DEFAULT_IMAGE_SIZE="4"
readonly TODAY=$(date +"%Y%m%d")
readonly DEFAULT_IMAGE_FILENAME="giftstick-${TODAY}.img"
FLAGS_REMASTERED_ISO=
FLAGS_SKIP_IMAGE=false
FLAGS_SKIP_ISO_REMASTER=false
FLAGS_SKIP_GCS=false
FLAGS_BUILD_TEST=false
FLAGS_SA_JSON_PATH=""

# Hardcoded paths
POST_UBUNTU_ROOT_SCRIPT="${REMASTER_SCRIPTS_DIR}/post-install-root.sh"
POST_UBUNTU_USER_SCRIPT="${REMASTER_SCRIPTS_DIR}/post-install-user.sh"
readonly TMP_MNT_POINT=$(mktemp -d)

readonly CONFIG_FILENAME="config.sh"

# Global variables
# TODO: let the user change these
readonly REMASTERED_SUFFIX="remastered"
# Name of the service account
readonly GCS_SA_NAME="giftstick"

# Checks that there is enough space left to work
#
# Arguments:
#  The work directory, as string.
function check_available_space {
  local workdir=$1
  local available_gb
  local required_gb
  available_gb=$(df -BG --output=avail "$workdir" | tail -1 | cut -d "G" -f1)
  available_gb=$(df -BG --output=avail "$workdir" | tail -1 | cut -d "G" -f1)
  if [[ $available_gb -lt $required_gb ]]; then
    die "Not enough space left in ${workdir} (${available_gb} < 2 * ${DEFAULT_IMAGE_SIZE}GB"
  fi
}

# Prints a message
#
# Arguments:
#  Message to display, as string.
function msg {
  local input=$1
  printf '* %s\n' "${input/${CURRENT_DIR}/.}" >&2
}

# Displays the banner
function show_banner {
  cat <<EOBANNER

           .......ll,,
          d. GIFT    .d
          X.   STICK .X
          'X.........N'
              odx,
              ,:
            .,;
           .o.
          .o'
         .o;
        'o;
       ,o;  Please grab a beverage of your liking, this may take up to AU/c...
      ,o;
     ;O;

EOBANNER
}

# Displays the help message
function show_usage {
  echo "
Usage: remaster.sh [OPTIONS]
Generates a new GiftStick image.

Example use:

  bash remaster.sh --source_iso xubuntu-20.04-desktop-amd64.iso --project your_gcp_project --bucket gcs_bucketname

Mandatory flags:
  --source_iso=ISO      The vanilla LiveCD to use as a base for the Gift OS
  --project=PROJECT     Sets the GCS project name
  --bucket=BUCKET       The destination GCS bucket name. If the bucket doesn't
                        exist, it will be created and ACL sets.

Optional flags
  -h, --help            Show this help message
  --sa_json_file        If provided, will use this file for the GCS service
                        account credentials, and won't try to create one.
  --image=IMAGE         Set the output filename to IMAGE
  --remastered_iso=ISO  Path to the remastered ISO (used if --skip_iso is
                        enabled)
  --skip_gcs            If set, will skip GCS environment setup
  --skip_image          If set, will skip the Gift image build
  --skip_iso            If set, will skip the ISO remastering"
}

# Make sure that FLAGS_CLOUD_PROJECT_NAME is defined
function assert_project_flag {
  if [[ ! "${FLAGS_CLOUD_PROJECT_NAME}" ]]; then
    if [[ "${FLAGS_SKIP_IMAGE}" == "false" ]]; then
      die "Please specify a cloud project name with --project"
    fi
  fi
}

# Make sure that FLAGS_SOURCE_ISO is defined
function assert_sourceiso_flag {
  if [[ "${FLAGS_SKIP_ISO_REMASTER}" == "false" ]]; then
    if [[ ! "${FLAGS_SOURCE_ISO}" ]]; then
      die "Please specify a source ISO to remaster with --source_iso"
    fi
    if [[ ! -f "${FLAGS_SOURCE_ISO}" ]]; then
      die "${FLAGS_SOURCE_ISO} is not found"
    fi
    if [[ "${FLAGS_SOURCE_ISO}" != *xubuntu* ]]; then
      echo "WARNING: This auto-remastering tool will probably not behave properly on a non xubuntu image"
      echo "press enter to continue anyway."
      read -r
    fi
    SOURCE_ISO=$(readlink -m "${FLAGS_SOURCE_ISO}")
  else
    if [[ ! "${FLAGS_REMASTERED_ISO}" ]]; then
      die "Please specify a remastered ISO with --remastered_iso"
    fi
  fi
}

# Make sure that FLAGS_IMAGE_FILENAME is defined
function assert_image_flag {
  if [[ ! "${FLAGS_IMAGE_FILENAME}" ]]; then
    FLAGS_IMAGE_FILENAME=$DEFAULT_IMAGE_FILENAME
  fi
}

# Make sure that FLAGS_IMAGE_SIZE is defined
function assert_image_size_flag {
  if [[ ! "${FLAGS_IMAGE_SIZE}" ]]; then
    FLAGS_IMAGE_SIZE=$DEFAULT_IMAGE_SIZE
  fi
}

# Check FLAGS_GCS_BUCKET_NAME against Bucket Name Requirements:
# https://cloud.google.com/storage/docs/naming#requirements
function assert_bucket_name {
  if [[ ! "${FLAGS_GCS_BUCKET_NAME}" ]]; then
    die "Please specify a GCS bucket name with --bucket"
  fi
  if [[ ${#FLAGS_GCS_BUCKET_NAME} -lt 3 ]]; then
    die "${FLAGS_GCS_BUCKET_NAME} is too short for a Bucket Name (<3)"
  fi
  if [[ ${#FLAGS_GCS_BUCKET_NAME} -gt 63 ]]; then
    die "${FLAGS_GCS_BUCKET_NAME} is too long for a Bucket Name (>63)"
  fi
  if [[ ${FLAGS_GCS_BUCKET_NAME} = *"goog"* ]]; then
    die "${FLAGS_GCS_BUCKET_NAME} can't contain 'goog'"
  fi
  if [[ ! ${FLAGS_GCS_BUCKET_NAME} =~ ^[a-z0-9][a-z0-9_-]+[a-z0-9]$ ]]; then
    echo -n "A bucket name can contain lowercase alphanumeric characters, "
    echo "hyphens."
    echo "Bucket names must start and end with an alphanumeric character."
    die "Wrong bucket name : ${FLAGS_GCS_BUCKET_NAME}"
  fi
}

# Make sure that GCS_SA_NAME is not too long
function assert_sa_name {
  if [[ ${#GCS_SA_NAME} -gt 30 ]]; then
    die "${GCS_SA_NAME} is too long for a Service Account name (>30)"
  fi
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

      --bucket)
        assert_option_argument "$2" "--bucket"
        FLAGS_GCS_BUCKET_NAME="$2"
        shift
        ;;
      --bucket=?*)
        FLAGS_GCS_BUCKET_NAME=${1#*=}
        ;;
      --bucket=)
        die '--bucket requires a non-empty option argument.'
        ;;

      --extra_gcs_path)
        assert_option_argument "$2" "--extra_gcs_path"
        FLAGS_EXTRA_GCS_PATH="$2"
        shift
        ;;
      --extra_gcs_path=?*)
        FLAGS_EXTRA_GCS_PATH=${1#*=}
        ;;
      --extra_gcs_path=)
        die '--extra_gcs_path requires a non-empty option argument.'
        ;;

      --image)
        assert_option_argument "$2" "--image"
        FLAGS_IMAGE_FILENAME="$2"
        shift
        ;;
      --image=?*)
        FLAGS_IMAGE_FILENAME=${1#*=}
        ;;
      --image=)
        die '--image requires a non-empty option argument.'
        ;;

      --project)
        assert_option_argument "$2" "--project"
        FLAGS_CLOUD_PROJECT_NAME="$2"
        shift
        ;;
      --project=?*)
        FLAGS_CLOUD_PROJECT_NAME=${1#*=}
        ;;
      --project=)
        die '--project requires a non-empty option argument.'
        ;;

      --remastered_iso)
        assert_option_argument "$2" "--remastered_iso"
        FLAGS_REMASTERED_ISO="$2"
        shift
        ;;
      --remastered_iso=?*)
        FLAGS_REMASTERED_ISO="$2"
        ;;
      --remastered_iso=)
        die '--remaster_iso requires a non-empty option argument.'
        ;;

      --skip_image)
        FLAGS_SKIP_IMAGE=true
        ;;

      --skip_iso)
        FLAGS_SKIP_ISO_REMASTER=true
        ;;

      --skip_gcs)
        FLAGS_SKIP_GCS=true
        ;;

      --sa_json_file)
        assert_option_argument "$2" "--sa_json_file"
        FLAGS_SA_JSON_PATH="$2"
        shift
        ;;
      --sa_json_file=?*)
        FLAGS_SA_JSON_PATH=${1#*=}
        ;;
      --sa_json_file=)
          die '--sa_json_file requires a non-empty option argument.'
        ;;

      --e2e_test)
        FLAGS_BUILD_TEST=true
        POST_UBUNTU_ROOT_SCRIPT="${REMASTER_SCRIPTS_DIR}/e2e/post-install-root.sh"
        POST_UBUNTU_USER_SCRIPT="${REMASTER_SCRIPTS_DIR}/e2e/post-install-user.sh"
        ;;

      --source_iso)
        assert_option_argument "$2" "--source_iso"
        FLAGS_SOURCE_ISO="$2"
        shift
        ;;
      --source_iso=?*)
        FLAGS_SOURCE_ISO=${1#*=}
        ;;
      --source_iso=)
          die '--source_iso requires a non-empty option argument.'
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

  # Verify arguments and set defaults.
  if [[ "${FLAGS_SKIP_GCS}" == "false" ]]; then
   assert_project_flag
   assert_bucket_name
   assert_sa_name
  fi
  assert_sourceiso_flag
  if [[ "${FLAGS_SKIP_ISO_REMASTER}" == "false" ]]; then

    readonly UBUNTU_ISO=$(readlink -m "${FLAGS_SOURCE_ISO}")
    if [[ ! "${FLAGS_REMASTERED_ISO}" ]] ; then
      readonly FLAGS_REMASTERED_ISO=$(basename "${UBUNTU_ISO}.${REMASTERED_SUFFIX}")
    fi
  fi

  if [[ "${FLAGS_SKIP_IMAGE}" == "false" ]]; then
    assert_image_flag
    assert_image_size_flag
    readonly GCS_REMOTE_URL="gs://${FLAGS_GCS_BUCKET_NAME}/forensic_evidence/${FLAGS_EXTRA_GCS_PATH}"

    # This checks agains a valid GCS object URL, such as
    # gs://bucket/path/to/file
    # See https://cloud.google.com/storage/docs/naming
    if [[ ! "${GCS_REMOTE_URL}" =~ ^gs://[a-zA-Z0-9_\.-]{3,63}(/[a-zA-Z0-9_\.\-]*/?)*$ ]] ; then
      die "${GCS_REMOTE_URL} is not a valid GCS URL"
    fi

    if [[ -z "${FLAGS_SA_JSON_PATH}" ]] ; then
      if [[ "${FLAGS_SKIP_GCS}" == "true" ]]; then
        die "Please provide path to a valid service account credentials file with --sa_json_file"
      fi
      readonly GCS_SA_KEY_NAME="${GCS_SA_NAME}_${FLAGS_CLOUD_PROJECT_NAME}_key.json"
      readonly GCS_SA_KEY_PATH="${REMASTER_SCRIPTS_DIR}/${GCS_SA_KEY_NAME}"
    else
      assert_sa_json_path "${FLAGS_SA_JSON_PATH}"
      readonly GCS_SA_KEY_PATH="$(readlink -m "${FLAGS_SA_JSON_PATH}")"
      readonly GCS_SA_KEY_NAME="$(basename "${FLAGS_SA_JSON_PATH}")"
    fi
  fi
}

# Builds the remaster LiveCD iso file.
#
# Arguments:
#  Source iso directory, as string.
#  Target iso file, as string.
function pack_iso {
  local -r source_iso_dir=$1
  local -r target_iso_file=$2

  msg "Packing the new ISO from ${source_iso_dir} to ${target_iso_file}"
  sudo genisoimage -o "${target_iso_file}" \
    -b "isolinux/isolinux.bin" \
    -c "isolinux/boot.cat" \
    -p "GiftStick" \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -V "GIFTSTICK-${TODAY}" -cache-inodes -r -J -l \
    -x "${source_iso_dir}"/casper/manifest.diff \
    -joliet-long \
    "${source_iso_dir}"
  sudo isohybrid "${target_iso_file}"
}

# Unpack a LiveCD iso file to a directory.
#
# Arguments:
#  Source iso file, as string.
#  Target directory, as string.
function unpack_iso {
  local -r iso_file=$1
  local -r iso_unpack_dir=$2
  local -r iso_mountpoint="${REMASTER_WORKDIR_PATH}/remaster-iso-mount"

  msg "unpacking iso ${iso_file} to ${iso_unpack_dir}"
  mkdir "${iso_mountpoint}"
  sudo mount -o ro,loop "${iso_file}" "${iso_mountpoint}"
  sudo cp -a "${iso_mountpoint}" "${iso_unpack_dir}"
  sudo umount "${iso_mountpoint}"
}

# Builds the root environment SquashFS file.
#
# Arguments:
#  Source directory for root filesystem, as string.
#  The future ISO root directory, where /casper/filesystem.squashfs will be
#    written, as string.
function pack_rootfs {
  local -r rootfs_dir=$1
  local -r target_iso_dir=$2
  local -r squashfs_image="${target_iso_dir}/casper/filesystem.squashfs"
  msg "Packing the modified rootfs from ${rootfs_dir} to ${squashfs_image}"
  msg "Updating files lists"
  sudo chroot "${rootfs_dir}" dpkg-query -W --showformat='${Package} ${Version}\n' | sudo tee -a "${target_iso_dir}/casper/filesystem.manifest" > /dev/null
  sudo cp "${target_iso_dir}/casper/filesystem.manifest" "${target_iso_dir}/casper/filesystem.manifest-desktop"
  msg "Packing SquashFS image (this will take a while)"
  sudo rm -f "${squashfs_image}"
  sudo mksquashfs "${rootfs_dir}" "${squashfs_image}" -comp xz
}

# Unpacks the root environment SquashFS file.
#
# Arguments:
#  The unpacked ISO root directory, contianing /casper/filesystem.squashfs, as string.
#  Target directory for the root filesystem, as string.
function unpack_rootfs {
  local -r unpacked_iso_dir=$1
  local -r dest_rootfs_dir=$2
  local -r squashfs_mountpoint="${REMASTER_WORKDIR_PATH}/remaster-root-mount"
  local -r squashfs_image="${unpacked_iso_dir}/casper/filesystem.squashfs"
  msg "Unpacking rootfs from ${squashfs_image} to ${dest_rootfs_dir}"
  mkdir "${squashfs_mountpoint}"
  msg "Mounting squashfs from ${squashfs_image} to ${squashfs_mountpoint}"
  sudo modprobe squashfs
  sudo mount -t squashfs -o loop "${squashfs_image}" "${squashfs_mountpoint}"
  msg "Copying squashfs (this may take a while)"
  sudo cp -a "${squashfs_mountpoint}"/. "${dest_rootfs_dir}"
  sudo umount "${squashfs_mountpoint}"
  sudo rmdir "${squashfs_mountpoint}"
}

# Prepares the chroot environment by mounting the usual pseufo-filesystems
#
# Arguments:
#  The target chroot directory, as string.
function mount_pseudo_fs {
   local -r chroot_dest="$1"

  msg "Preparing ${chroot_dest} for chroot"
  sudo mkdir -p "${chroot_dest}/proc"
  sudo mount --bind /proc "${chroot_dest}/proc"
  sudo mkdir -p "${chroot_dest}/sys"
  sudo mount --bind /sys "${chroot_dest}/sys"
  sudo mkdir -p "${chroot_dest}/dev/pts"
  sudo mount --bind /dev/pts "${chroot_dest}/dev/pts"
  sudo mkdir -p "${chroot_dest}/tmp"
  sudo mount --bind /tmp "${chroot_dest}/tmp"
}

# Cleans up the chroot environment by unmounting the usual pseufo-filesystems
#
# Arguments:
#  The chroot directory, as string.
function unmount_pseudo_fs {
  local -r root_mount=$1
  msg "Unmounting pseudo-FS in ${root_mount}"
  local mount_point
  for mount_point in $(mount | grep " ${root_mount}" | cut -d " " -f3 ); do
    sudo umount -l "${mount_point}"
  done
}

# Chroots into the target root filesystem, and execute a script
#
# Arguments:
#  The chroot directory, as string.
#  The script to execute, as string.
function chroot_rootfs {
  local -r chroot_dir=$1
  local -r script=$2
  msg "Chroot in ${chroot_dir} and execute ${script}"
  mount_pseudo_fs "${chroot_dir}"
  sudo chroot "${chroot_dir}" "${script}"
  unmount_pseudo_fs "${chroot_dir}"
}

# Cleans up all remastering working directories.
function clean_all_remaster_directories {
  msg "Cleaning up"
  unmount_pseudo_fs "${remaster_destroot_dir}"
  sudo rm -rf "${remaster_destroot_dir}"
  sudo rm -rf "${remaster_destiso_dir}"
}

# Creates a remastered ISO LiveCD with the required customizations.
# The generated remastered ISO will be available in the current directory.
function make_custom_ubuntu_iso {
  # Let's define some directories for all the remaster subfunctions
  readonly remaster_destiso_dir="${REMASTER_WORKDIR_PATH}/remaster-iso"
  readonly remaster_destroot_dir="${REMASTER_WORKDIR_PATH}/remaster-root"

  local post_ubuntu_script_name

  msg "Making a custom ISO image from $(basename "${SOURCE_ISO}")"

  unpack_iso "${SOURCE_ISO}" "${remaster_destiso_dir}"
  mkdir "${remaster_destroot_dir}"
  unpack_rootfs "${remaster_destiso_dir}" "${remaster_destroot_dir}"

  if [[ -f "${POST_UBUNTU_ROOT_SCRIPT}" ]] ; then
    post_ubuntu_script_name=$(basename "${POST_UBUNTU_ROOT_SCRIPT}")
    msg "Executing ${post_ubuntu_script_name}"
    sudo cp "${POST_UBUNTU_ROOT_SCRIPT}" "${remaster_destroot_dir}/"
    sudo chmod u+x "${remaster_destroot_dir}/${post_ubuntu_script_name}"
    chroot_rootfs "${remaster_destroot_dir}" "/${post_ubuntu_script_name}"
  fi
  pack_rootfs "${remaster_destroot_dir}" "${remaster_destiso_dir}"
  pack_iso "${remaster_destiso_dir}" "${FLAGS_REMASTERED_ISO}"

  msg "Generating md5sum for newly created ISO"
  md5sum "${FLAGS_REMASTERED_ISO}" > "${FLAGS_REMASTERED_ISO}.md5"

  clean_all_remaster_directories

  sudo chown "${EUID}" "${FLAGS_REMASTERED_ISO}"
  sudo chown "${EUID}" "${FLAGS_REMASTERED_ISO}.md5"
  sudo rm -rf --one-file-system "${REMASTER_WORKDIR_PATH}"
  msg "Your new ISO ${FLAGS_REMASTERED_ISO} is ready to be used."
}

# Creates a bucket the Bucket
#
# Arguments:
#   The bucket name, as string
function create_bucket {
  local bucket=$1
  if gsutil -q ls -p "${FLAGS_CLOUD_PROJECT_NAME}" "gs://" | grep -q "gs://${bucket}/"; then
    msg "Bucket ${bucket} already exists in project ${FLAGS_CLOUD_PROJECT_NAME}"
  else
    gsutil mb -p "${FLAGS_CLOUD_PROJECT_NAME}" "gs://${bucket}/"
  fi
}

# Creates a Service Account
#
# Arguments:
#  The target bucket name, as string
#  The Service Account name, as string.
function create_service_account {
  local gcs_bucket_name=$1
  local gcs_sa_name=$2
  local gcs_sa_email="${gcs_sa_name}@${FLAGS_CLOUD_PROJECT_NAME}.iam.gserviceaccount.com"
  if gcloud -q iam service-accounts list --project "${FLAGS_CLOUD_PROJECT_NAME}" --format "get(email)" | grep -q "${gcs_sa_email}"; then
    msg "${gcs_sa_email} already exists in project ${FLAGS_CLOUD_PROJECT_NAME}. Reusing."
  else
    gcloud -q iam service-accounts create "${gcs_sa_name}" \
      --project "${FLAGS_CLOUD_PROJECT_NAME}" --display-name "${gcs_sa_name}"
    # Enable logging
    gcloud projects add-iam-policy-binding "${FLAGS_CLOUD_PROJECT_NAME}" \
      --member "serviceAccount:${gcs_sa_email}" --role "roles/logging.logWriter"
  fi
  # Give the SA create permissions
  gsutil iam ch "serviceAccount:${gcs_sa_email}:objectCreator" "gs://${gcs_bucket_name}"
}

# Creates and downloads a service account private key
#
# Arguments:
#   The target bucket.
#   The service account name.
#   The path to the private key file, as string.
function create_sa_key {
  local gcs_bucket_name=$1
  local gcs_sa_name=$2
  local gcs_sa_key_path=$3
  local -r gcs_sa_email="${gcs_sa_name}@${FLAGS_CLOUD_PROJECT_NAME}.iam.gserviceaccount.com"

  if [[ ! -f "${gcs_sa_key_path}" ]]; then
    gcloud iam service-accounts --project "${FLAGS_CLOUD_PROJECT_NAME}" keys create \
      --iam-account "${gcs_sa_email}" "${gcs_sa_key_path}"
  else
    msg "${gcs_sa_key_path} already exists. Reusing."
  fi
}

# Makes sure Gcloud stuff is present and user is logged in.
function check_gcs {
   if [[ "$(which gsutil)" == "" ]]; then
     die "Please install gsutil ( see https://cloud.google.com/storage/docs/gsutil_install ) "
   fi
   gcloud_accounts=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
   if [[ "${gcloud_accounts}" == "" ]]; then
     die "It looks like you're not logged in gcloud. Please run gcloud init"
   fi
}

# Sets up the GCS environment in the remote project, and generates the required
# credentials to be added later in the image.
function configure_gcs {
  msg "Preparing GCS environment"

  create_bucket "${FLAGS_GCS_BUCKET_NAME}"
  if [[ -z "$FLAGS_SA_JSON_PATH" ]] ; then
    create_service_account "${FLAGS_GCS_BUCKET_NAME}" "${GCS_SA_NAME}"
    create_sa_key "${FLAGS_GCS_BUCKET_NAME}" "${GCS_SA_NAME}" "${GCS_SA_KEY_PATH}"
  fi
}

# This function uses a LiveCD ISO image and creates a USB bootable image.
# The image will use a GPT partition scheme and boots with EFI/Grub.
# The scripts also runs the post-install-user.sh script if found.
# Argument:
#   The path to the remastered ISO to use.
function make_bootable_usb_image {
  local remastered_iso_filename
  local remastered_iso_path
  local kernel_name
  local loop_device

  remastered_iso_path=$1

  kernel_name="vmlinuz"

  if [[ ! -f "${remastered_iso_path}" ]]; then
    die "Remastered iso ${remastered_iso_path} not found"
  fi
  remastered_iso_filename=$(basename "${remastered_iso_path}")

  msg "Build a bootable USB image from ${remastered_iso_path}"
  msg "Create an empty image, and EFI + Persistence partitions"
  truncate -s "${FLAGS_IMAGE_SIZE}G" "${FLAGS_IMAGE_FILENAME}"
  sgdisk --zap-all  "${FLAGS_IMAGE_FILENAME}"
  sgdisk --new=1:0:+2G --typecode=1:ef00 "${FLAGS_IMAGE_FILENAME}" # This will hold the system's ISO
  sgdisk --largest-new=2 --typecode=2:8300 "${FLAGS_IMAGE_FILENAME}" # this will be the persistent partition

  msg "Mount the EFI partition"
  loop_device=$(sudo losetup -fP --show "${FLAGS_IMAGE_FILENAME}")
  sudo mkfs.vfat "${loop_device}p1"
  sudo mkfs.ext3 -L casper-rw "${loop_device}p2"
  sudo mount "${loop_device}p1" "${TMP_MNT_POINT}"

  msg "Install some EFI Magic"
  sudo mkdir -p "${TMP_MNT_POINT}/EFI/BOOT"
  sudo mkdir -p "${TMP_MNT_POINT}/boot/grub"
  sudo mkdir "${TMP_MNT_POINT}/iso"
  sudo cp "${remastered_iso_path}" "${TMP_MNT_POINT}/iso/"
  # Create the UEFI default entry
  sudo grub-install --removable --target=x86_64-efi \
    --efi-directory="${TMP_MNT_POINT}" \
    --boot-directory="${TMP_MNT_POINT}/boot/" "${loop_device}"

  # Create an entry named "GIFT"
  sudo mkdir -p "${TMP_MNT_POINT}/GIFT"
  sudo cp -a "${TMP_MNT_POINT}/EFI/BOOT" "${TMP_MNT_POINT}/GIFT"

  msg "Install some GRUB Magic"
  # Fix for the "no suitable mode found" error
  sudo cp /usr/share/grub/unicode.pf2 "${TMP_MNT_POINT}/boot/grub/"

  cat << EOGRUB | sudo tee "${TMP_MNT_POINT}/boot/grub/grub.cfg" > /dev/null
set default=0
set timeout=5

insmod efi_gop
insmod efi_uga

insmod font

if loadfont /boot/grub/fonts/unicode.pf2
then
    insmod gfxterm
    set gfxmode=auto
    set gfxpayload=keep
    terminal_output gfxterm
fi

menuentry 'Ubuntu/Gift' {
  set isofile="/iso/${remastered_iso_filename}"
  loopback loop \$isofile
  linux (loop)/casper/vmlinuz boot=casper iso-scan/filename=\$isofile liveimg noprompt noeject quiet splash persistent --
  initrd (loop)/casper/initrd
}
EOGRUB

  sudo umount "${TMP_MNT_POINT}"

  msg "Customize user directory"
  sudo mount "${loop_device}p2" "${TMP_MNT_POINT}"
  sudo mkdir -p "${TMP_MNT_POINT}/upper/home/${GIFT_USERNAME}/"

  pushd "${TMP_MNT_POINT}/upper/home/${GIFT_USERNAME}/"

  sudo cp "${GCS_SA_KEY_PATH}" .

  sudo cp "${FORENSICATE_SCRIPT_PATH}" "${FORENSICATE_SCRIPT_NAME}"

  cat <<EOFORENSICSH | sudo tee -a "${CONFIG_FILENAME}" > /dev/null
AUTO_FORENSIC_SCRIPT_NAME="${AUTO_FORENSIC_SCRIPT_NAME}"
GCS_SA_KEY_FILE="/home/${GIFT_USERNAME}/${GCS_SA_KEY_NAME}"
GCS_REMOTE_URL="${GCS_REMOTE_URL}"
EOFORENSICSH

  if $FLAGS_BUILD_TEST ; then
    cat <<EOFORENSICSHEXTRA | sudo tee -a "${CONFIG_FILENAME}" > /dev/null
      EXTRA_OPTIONS="--disk sdb"
EOFORENSICSHEXTRA
  fi

  if [[ -f "${POST_UBUNTU_USER_SCRIPT}" ]] ; then
    # shellcheck source=remaster_scripts/post-install-user.sh
    . "${POST_UBUNTU_USER_SCRIPT}"
  else
    msg "No user directory customization \
      (POST_UBUNTU_USER_SCRIPT=\"${POST_UBUNTU_USER_SCRIPT}\" not found)"
  fi

  popd

  sudo chown -R 999:999 "${TMP_MNT_POINT}/upper/home/${GIFT_USERNAME}"

  msg "Cleaning up"
  if [[ "${FLAGS_SKIP_GCS}" == "false" ]]; then
    if [[ ! -z "${FLAGS_SA_JSON_PATH}" ]] ; then
      sudo rm "${GCS_SA_KEY_PATH}"
    fi
  fi
  sudo umount "${TMP_MNT_POINT}"
  rmdir "${TMP_MNT_POINT}"
  sudo losetup -d "${loop_device}"
}

function main {
  # Create working directory if needed.
  mkdir -p "${REMASTER_WORKDIR_PATH}"
  # Check that we have required disk space, permission and packages.
  check_available_space "${REMASTER_WORKDIR_PATH}"

  # We disable set -e in order to display relevant error message when
  # checking for package instalation status.
  set +e
  check_packages gdisk
  check_packages genisoimage
  check_packages grub-efi-amd64-bin
  check_packages squashfs-tools
  check_packages syslinux
  check_packages syslinux-utils
  set -e

  parse_arguments "$@"

  show_banner

  if [[ "${FLAGS_SKIP_GCS}" == "false" ]]; then
    check_gcs
    configure_gcs
  fi

  if [[ ${FLAGS_SKIP_ISO_REMASTER} == "false" ]]; then
    make_custom_ubuntu_iso
    sync
  fi

  if [[ "${FLAGS_SKIP_IMAGE}" == "false" ]]; then
    make_bootable_usb_image "$FLAGS_REMASTERED_ISO"
    sync

    msg "All done ! Your new image is ${FLAGS_IMAGE_FILENAME}"
    msg "You can:"
    msg " - Test it in QEMU"
    msg "   qemu-system-x86_64 -cpu qemu64 -bios /usr/share/ovmf/OVMF.fd  \
-m 1024 -enable-kvm -drive format=raw,file='${FLAGS_IMAGE_FILENAME}' -device e1000,netdev=net0 -netdev user,id=net0"
    msg " - Write it to a removable device:"
    msg "   dd if=${FLAGS_IMAGE_FILENAME} bs=2M conv=fsync | \
pv -s ${FLAGS_IMAGE_SIZE}G > /dev/sdXXX"
    msg "Have a nice day!"
  fi
}

# This trap restores a clean environment. In case of failure, we won't have
# leftovers mounted filesystems.
function trap_cleanup {
  if [[ -d "${CURRENT_DIR}" ]]; then
    cd "${CURRENT_DIR}"
    mountpoint -q "${TMP_MNT_POINT}" && sudo -n umount "${TMP_MNT_POINT}"
    if [[ -f "${FLAGS_IMAGE_FILENAME}" ]]; then
      loop_devices=$(losetup -O NAME --noheadings -j "${FLAGS_IMAGE_FILENAME}")
      for loop_device in $loop_devices; do
        sudo losetup -d "${loop_device}"
      done
    fi
    if [[ -d "${TMP_MNT_POINT}" ]] ; then
      rmdir "${TMP_MNT_POINT}"
    fi
    if [[ ${FLAGS_SKIP_ISO_REMASTER} == "false" ]]; then
      echo "cleaning up remastering leftovers"
      if [[ -d "${remaster_destroot_dir}" ]]; then
        unmount_pseudo_fs "${remaster_destroot_dir}"
      fi
      if [[ -d "${REMASTER_WORKDIR_PATH}/remaster-iso-mount" ]]; then
        umount "${REMASTER_WORKDIR_PATH}/remaster-iso-mount"
      fi
      if [[ -d "${REMASTER_WORKDIR_PATH}" ]]; then
        unmount_pseudo_fs "${REMASTER_WORKDIR_PATH}"
      fi
      sudo rm -rf --one-file-system "${REMASTER_WORKDIR_PATH}"
    fi
  fi
}

trap "{
  trap_cleanup
}" INT EXIT


main "$@"
