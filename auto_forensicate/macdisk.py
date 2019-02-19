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
import xml.parsers.expat
import subprocess

class MacDiskError(Exception):
  """Module specific exception class."""
  pass

def RunProcess(cmd):
  """Executes cmd using suprocess.

  Args:
    cmd: An array of strings as the command to run
  Returns:
    Tuple: two strings and an integer: (stdout, stderr, returncode);
    stdout/stderr may also be None. If the process is set to launch in
    background mode, an instance of <subprocess.Popen object> is
    returned, in order to be able to read from its pipes *and* use poll() to
    check when it is finished.
  """
  try:
    task = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  except OSError as e:
    raise OSError('Could not execute: %s' % e.strerror)
  (stdout, stderr) = task.communicate()
  return (stdout, stderr, task.returncode)

def _DictFromSubprocess(command):
  """returns a dict based upon a subprocess call with a -plist argument.

  Args:
    command: the command to be executed as a list
  Returns:
    dict: dictionary from command output
  """

  task = {}

  (task['stdout'], task['stderr'], task['returncode']) = RunProcess(command)

  if task['returncode'] is not 0:
    raise MacDiskError(
        'Error running command: {0}, stderr: {1}' .format(
            command, task['stderr']))
  else:
    try:
      return plistlib.readPlistFromString(task['stdout'])
    except xml.parsers.expat.ExpatError:
      raise MacDiskError(
          'Error creating plist from output: {0}'.format(task['stdout']))

def _DictFromDiskutilInfo(deviceid):
  """calls diskutil info for a specific device id.

  Args:
    deviceid: a given device id for a disk like object
  Returns:
    info: dictionary from resulting plist output
  Raises:
    MacDiskError: deviceid is invalid
  """
  # Do we want to do this? can trigger optical drive noises...
  if deviceid not in PartitionDeviceIds():
    raise MacDiskError("%s is not a valid disk id" % deviceid)
  else:
    command = ["/usr/sbin/diskutil", "info", "-plist", deviceid]
    return _DictFromSubprocess(command)

def _DictFromDiskutilList():
  """calls diskutil list -plist and returns as dict."""

  command = ["/usr/sbin/diskutil", "list", "-plist"]
  return _DictFromSubprocess(command)

def PartitionDeviceIds():
  """Returns a list of all device ids that are partitions."""
  try:
    return _DictFromDiskutilList()["AllDisks"]
  except KeyError:
    # TODO(user): fix errors to actually provide info...
    raise MacDiskError("Unable to list all partitions.")

class Disk(object):
  """Represents a Mac disk object.

  Note that this also is used for currently mounted disk images as they
  really are just 'disks'. Mostly. Can take device ids of the form "disk1" or
  of the form "/dev/disk1".
  """

  def __init__(self, deviceid):
    if deviceid.startswith("/dev/"):
      deviceid = deviceid.replace("/dev/", "", 1)
    self.deviceid = deviceid
    self.Refresh()

  def Refresh(self):
    """convenience attrs for direct querying really."""

    self._attributes = _DictFromDiskutilInfo(self.deviceid)
    # We iterate over all known keys, yes this includes DeviceIdentifier
    # even though we"re using deviceid internally for init.
    # This is why the rest of the code has gratuitous use of
    # disable-msg=E1101 due to constructing the attributes this way.
    keys = ["Content", "Internal", "CanBeMadeBootableRequiresDestroy",
            "MountPoint", "DeviceNode", "SystemImage", "CanBeMadeBootable",
            "SupportsGlobalPermissionsDisable", "VolumeName",
            "DeviceTreePath", "DeviceIdentifier", "VolumeUUID", "Bootable",
            "BusProtocol", "Ejectable", "MediaType", "RAIDSlice",
            "FilesystemName", "RAIDMaster", "WholeDisk", "FreeSpace",
            "TotalSize", "GlobalPermissionsEnabled", "SMARTStatus",
            "Writable", "ParentWholeDisk", "MediaName"]

    for key in keys:
      try:
        attribute = key.lower().replace(" ", "")
        setattr(self, attribute, self._attributes[key])
      except KeyError:  # not all objects have all these attributes
        pass

    if self.busprotocol == "Disk Image":  # pylint: disable=no-member
      self.diskimage = True
    else:
      self.diskimage = False
