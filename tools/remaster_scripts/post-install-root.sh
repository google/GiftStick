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

# This script is being run chrooted in the ubuntu live CD ISO image

function ubuntu_remove_packages {
  local PKG=( ubiquity udisks2 ) # udisks2 is responsible for automounting
  if [[ ${DISTRIB_CODENAME} == "trusty" ]]; then
    PKG+=( friends friends-dispatcher friends-facebook friends-twitter )
  fi
  apt-get -y remove "${BAD_PKG[@]}"
}

function install_forensication_tools {
  readonly local CHIPSEC_PKG=( python3-dev libffi-dev build-essential gcc nasm )
  readonly local FORENSIC_PKG=( dcfldd )

  # install common utils
  apt-get -y install "${FORENSIC_PKG[@]}" "${CHIPSEC_PKG[@]}"
}

function install_basic_pkg {
  readonly local COMMON_UTILS=( git jq python3-pip pv zenity )
  readonly local WIRELESS_PKG=( firmware-b43-installer bcmwl-kernel-source )

  apt-get -y update
  apt-get -y install "${COMMON_UTILS[@]}" "${WIRELESS_PKG[@]}"

  echo "PasswordAuthentication no" >>  /etc/ssh/sshd_config

  # Force python3
  update-alternatives --install /usr/bin/python python /usr/bin/python3 1
  update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

}

function ubuntu_fix_systemd {
  # By default, with systemd, /etc/resolv.conf is a link to
  # /run/systemd/resolve/resolve.conf, which is only created when
  # systemd-resoved has successfully started.
  # Since we're going to chroot, the link will be broken and we'll get no DNS
  # resolution. So we make our own temporary static resolv.conf here.
  if [[ -L /etc/resolv.conf ]]; then
    rm /etc/resolv.conf
    echo "nameserver 8.8.8.8" > /etc/resolv.conf.static
    ln -s /etc/resolv.conf.static /etc/resolv.conf
  fi

  # Systemd fails if DNSSEC fails by default. So we disable that
  if [[ -f /etc/systemd/resolved.conf ]]; then
    sed -i 's/^#DNSSEC=.*/DNSSEC=no/' /etc/systemd/resolved.conf
  fi
  apt-get -y install libnss-resolve
}

function ubuntu_fix_mbp {

  # This is installing SPI drivers for the keyboard & mousepads on
  # MacBook 2016 (with touchbar)
  apt-get -y install dkms
  git clone https://github.com/cb22/macbook12-spi-driver.git /usr/src/applespi-0.1

  # We need to install for the kernel of the OS we're chrooted in, not the one
  # that's currently running on our workstation.
  # Ubuntu Live CD should only have one kernel installed, so this should work.
  dkms install -m applespi -v 0.1 -k "$(basename /lib/modules/*)"
  echo -e "\napplespi\nintel_lpss_pci\nspi_pxa2xx_platform" >> /etc/initramfs-tools/modules
  update-initramfs -u
}

function ignore_chipsec_logs {
  # Chipsec generates a ton of logs which can fill up the local storage
  echo -e ":msg, contains, \"IOCTL_RDMMIO\" stop\n\
:msg, contains, \"IOCTL_WRMMIO\" stop\n\
& stop" > /etc/rsyslog.d/00-chipsec.conf
}

# Comment out cdrom repo
sed -e '/cdrom/ s/^#*/#/' -i /etc/apt/sources.list

source /etc/lsb-release

if ! [[ "xenial" == "${DISTRIB_CODENAME}" ]]; then
  ubuntu_fix_systemd
fi

ignore_chipsec_logs
install_basic_pkg
install_forensication_tools
ubuntu_remove_packages
ubuntu_fix_mbp
