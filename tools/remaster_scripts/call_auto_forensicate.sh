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

source config.sh

# Make sure have the latest version of the auto_forensicate module
git clone https://github.com/google/GiftStick
cd GiftStick
sudo python setup.py install

# Apply patch for boto py3 compatibility
# See https://github.com/boto/boto/pull/3699
boto_dir=$(python -c "import boto; print(boto.__path__[0])")

if grep -qe "sendall.*encode" "${boto_dir}/connection.py" ; then
  echo "skipping patching of ${boto_dir}/connection.py"
else
  echo "patching ${boto_dir}/connection.py"
  sudo patch -p0 "${boto_dir}/connection.py" config/patches/boto_pr3561_connection.py.patch
fi

if grep -qe "send.*encode" "${boto_dir}/s3/key.py" ; then
  echo "skipping patching of ${boto_dir}/s3/key.py"
else
  echo "patching ${boto_dir}/s3/key.py"
  sudo patch -p0 "${boto_dir}/s3/key.py" config/patches/boto_pr3561_key.py.patch
fi


# We need to build a module for this system, this can't be installed before
# booting.
sudo pip install chipsec

sudo "${AUTO_FORENSIC_SCRIPT_NAME}" \
  --gs_keyfile="${GCS_SA_KEY_FILE}" \
  --logging stdout \
  --acquire all \
  ${EXTRA_OPTIONS} "${GCS_REMOTE_URL}/"
