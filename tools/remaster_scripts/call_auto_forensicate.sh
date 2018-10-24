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

# Base forensication script.
# This is customized by the master remaster script.

# First, check that we have internet
wget -q --spider http://www.google.com
if [[ $? -ne 0 ]]; then
  echo "ERROR: No internet connectivity"
  echo "Please make sure the system is connected to the internet"
  exit 1
fi

# Make sure have the latest version of the auto_forensicate module
git clone https://github.com/google/GiftStick
cd GiftStick
sudo python setup.py install

# We need to build a module for this system, this can't be installed before
# booting.
sudo pip install chipsec

