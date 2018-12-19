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

function add_test_ssh_key {
  sudo mkdir .ssh
  echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHx26PEzEj5WIZDP/Actr4LruAiIFbVP4hS8ANBrcnnH e2etests" | sudo tee -a .ssh/authorized_keys
}

add_test_ssh_key
