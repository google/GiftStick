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
"""Helpers class for accessing system information."""

from __future__ import unicode_literals

import os
import subprocess
import time
import uuid


def ReadDMI(name):
  """Reads a DMI value from the /sys filesystem.

  Args:
    name (str): the name of the DMI value to read.

  Returns:
    str: the DMI value, or None if not available.
  """
  dmi_value = None
  dmi_path = os.path.join('/sys/class/dmi/id/', name)
  try:
    with open(dmi_path, 'r') as d_f:
      dmi_value = d_f.read().strip()
  except IOError:
    pass
  return dmi_value


def GetChassisSerial():
  """Gets the system's chassis serial number.

  Returns:
    str: the serial number.
  """
  return ReadDMI('chassis_serial')


def GetSystemInformation():
  """Gets the system's hardware information.

  Returns:
    str: the information, outputs of dmidecode, or None.
  """
  dmi_info = None
  try:
    dmi_info = subprocess.check_output(['dmidecode', '--type=system'])
  except subprocess.CalledProcessError:
    pass
  return dmi_info


def GetMachineUUID():
  """Gets the system's product UUID.

  Returns:
    str: the product UUID.
  """
  return ReadDMI('product_uuid')


def GetRandomUUID():
  """Generates a random UUID.

  Returns:
    str: the UUID.
  """
  return str(uuid.uuid4())


def GetIdentifier():
  """Gets an identifier for the machine.

  It first tries to use the machine's serial number, then the machine's UUID,
  and defaults to a random UUID.

  Returns:
    str: the identifier.
  """
  identifier = (GetChassisSerial() or
                GetMachineUUID() or
                GetRandomUUID())
  return identifier


def GetUdevadmInfo(device_name):
  """Uses udevadm to pull metadata for a device.

  Args:
    device_name(str): the name of the device. ie: 'sda'

  Returns:
    dict: a dictionary of udev properties.
  """
  device_metadata = {}
  cmd = ['/sbin/udevadm', 'info', '--query', 'property', '--name', device_name]
  udevadm_output = subprocess.check_output(cmd)
  device_metadata['udevadm_text_output'] = udevadm_output
  for line in udevadm_output.split('\n'):
    try:
      key, value = line.strip().split('=', 1)
      device_metadata[key] = value
    except ValueError:
      pass
  return device_metadata


def GetTime():
  """Returns the current time as a iso string."""
  return time.strftime('%Y%m%d-%H%M%S', time.gmtime())
