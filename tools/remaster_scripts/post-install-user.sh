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

# Does customization for the xubuntu user
# The script is run as sudoer on your workstation, permissions are fixed
# later.


function user_customise_desktop {

  sudo mkdir -p Desktop

  sudo mkdir -p .config/xfce4/xfconf/xfce-perchannel-xml
  cat << EOXFCONF | sudo tee ".config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
<?xml version="1.0" encoding="UTF-8"?>

<channel name="xfce4-desktop" version="1.0">
  <property name="desktop-icons" type="empty">
    <property name="file-icons" type="empty">
      <property name="show-home" type="bool" value="false"/>
      <property name="show-filesystem" type="bool" value="false"/>
      <property name="show-removable" type="bool" value="false"/>
      <property name="show-trash" type="bool" value="false"/>
    </property>
    <property name="show-thumbnails" type="bool" value="true"/>
  </property>
</channel>
EOXFCONF


  # Install click-able shortcut on Desktop
  cat << EOCHIPSHORT | sudo tee "Desktop/auto_forensicate.desktop" > /dev/null
[Desktop Entry]
Version=1.0
Type=Application
Name=Forensicate!
Comment=Runs forensics acquisition and upload to GCS
Exec=bash -c 'sudo bash call_auto_forensicate.sh; $SHELL'
Icon=applications-utilities
Terminal=true
StartupNotify=false
EOCHIPSHORT

  sudo chmod a+x "Desktop/auto_forensicate.desktop"

}

user_customise_desktop
