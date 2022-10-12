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
"""Helper functions to handle Mac OS information."""

import plistlib
import subprocess
import sys


class MacDiskError(Exception):
  """Module specific exception class."""


def _DictFromSubprocess(command):
  """Returns a dict based upon a subprocess call with a -plist argument.

  Args:
    command(list(str)): the command to be executed as a list.
  Returns:
    dict: dictionary from command output.
  Raises:
    MacDiskError: if the command failed to run.
  """

  try:
    task = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  except OSError as e:
    raise MacDiskError('Could not execute: {0:s}'.format(e.strerror))
  (stdout, stderr) = task.communicate()

  if task.returncode != 0:
    raise MacDiskError(
        'Error running command: {0:s}, stderr: {1:s}' .format(
            ' '.join(command), stderr))

  try:
    return plistlib.loads(stdout)
  except Exception:
    raise MacDiskError(
        'Error creating plist from output: {0:s}'.format(stdout))


def _DictFromDiskutilInfo(deviceid):
  """Calls diskutil info for a specific device ID.

  Args:
    deviceid(string): a given device id for a disk like object.
  Returns:
    dict: resulting plist output.
  Raises:
    MacDiskError: if deviceid is invalid.
  """
  command = ['/usr/sbin/diskutil', 'info', '-plist', deviceid]
  return _DictFromSubprocess(command)


def _DictFromDiskutilList():
  """Calls diskutil list -plist and returns as dict.

  Returns:
    dict: resulting plist output
  """

  command = ['/usr/sbin/diskutil', 'list', '-plist']
  return _DictFromSubprocess(command)


def WholeDisks():
  """Returns a list of all disk objects that are whole disks."""
  wholedisks = []
  try:
    diskutil_dict = _DictFromDiskutilList()
    for deviceid in diskutil_dict['WholeDisks']:
      wholedisks.append(Disk(deviceid))
  except KeyError:
    raise MacDiskError('Unable to list all partitions.')
  return wholedisks


class Disk(object):
  """Represents a Mac disk object.

  Note that this also is used for currently mounted disk images as they
  really are just 'disks'. Mostly. Can take device ids of the form 'disk1' or
  of the form '/dev/disk1'.
  """

  def __init__(self, deviceid):
    """Initializes a MacDisk object.

    Args:
      deviceid(str): Name (or path) to a disk
    """
    if deviceid.startswith('/dev/'):
      deviceid = deviceid.replace('/dev/', '', 1)
    self.deviceid = deviceid
    self.Refresh()

  def Refresh(self):
    """Builds a list of convenience attributes for direct querying."""

    self._attributes = _DictFromDiskutilInfo(self.deviceid)
    # These are the keys we are interested in
    keys = ['Internal', 'DeviceIdentifier', 'BusProtocol', 'VirtualOrPhysical',
            'DeviceIdentifier', 'TotalSize']

    for key in keys:
      try:
        attribute = key.lower().replace(' ', '')
        setattr(self, attribute, self._attributes[key])
      except KeyError:  # not all objects have all these attributes
        pass
