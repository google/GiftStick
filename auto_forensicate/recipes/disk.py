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
"""Handles the acquisition of the raw disk image."""

from __future__ import unicode_literals

import json
import os
import subprocess

from auto_forensicate import errors
from auto_forensicate import hostinfo
from auto_forensicate.recipes import base
from auto_forensicate.ux import gui

try:
  # This is not in pip, can be installed from:
  # https://github.com/google/macops/tree/master/gmacpyutil
  # If not present, code should still run on a Linux machine.
  from gmacpyutil import macdisk
except ImportError:
  pass


class DiskArtifact(base.BaseArtifact):
  """The DiskArtifact class.

  Attributes:
    hashlog_filename (str): where dcfldd will store the hashes.
    name (str): the name of the artifact.
    remote_path (str): the path to the artifact in the remote storage.
    size (int): the size of the artifact, in bytes.
  """

  _DD_BINARY = '/usr/bin/dcfldd'
  _DD_OPTIONS = ['hash=md5,sha1', 'bs=2M', 'conv=noerror', 'hashwindow=128M']

  def __init__(self, path, size):
    """Initializes a DiskArtifact object.

    Only supported implementations are MacOS and Linux.

    Args:
      path(str): the path to the disk.
      size(str): the size of the disk.

    Raises:
      valueerror: if path is none, doesn't start with '/dev' or size is =< 0.
    """
    super(DiskArtifact, self).__init__(os.path.basename(path))
    if not path.startswith('/dev'):
      raise ValueError(
          'Error with path {0:s}: should start with \'/dev\''.format(path))
    self._ddprocess = None
    self._path = path
    if size > 0:
      self._size = size
    else:
      raise ValueError('Disk size must be an integer > 0')
    self.hashlog_filename = '{0:s}.hash'.format(self.name)
    self.remote_path = 'Disks/{0:s}.image'.format(self.name)

  def _GenerateDDCommand(self):
    """Builds the DD command to run on the disk.

    Returns:
      list: the argument list for the dd command
    """
    command = [
        self._DD_BINARY, 'if={0:s}'.format(self._path),
        'hashlog={0:s}'.format(self.hashlog_filename)]
    command.extend(self._DD_OPTIONS)
    return command

  def _GetStream(self):
    """Get the file-like object to the data of the artifact.

    Returns:
      file: Read-only file-like object to the data.

    Raises:
      IOError: If this method is called more than once before CloseStream().
    """
    if self._ddprocess is None:
      command = self._GenerateDDCommand()
      self._logger.info('Opening disk with command \'{0:s}\''.format(command))
      self._ddprocess = subprocess.Popen(
          command, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
      raise IOError('Disk is already opened')
    return self._ddprocess.stdout

  def CloseStream(self):
    """Closes the file-like object.

    Returns:
      str: a return message for the report.

    Raises:
      subprocess.CalledProcessError: if the dd process returns with an error.
      IOError: if CloseStream() is called before GetStream().
    """
    if not self._ddprocess:
      raise IOError('Illegal call to CloseStream() before GetStream()')

    # If there is anything still to read from the subprocess then CloseStream
    # has been called early, terminate the child process to avoid deadlock.
    c = self._ddprocess.stdout.read(1)
    if c != '':
      # TODO log this
      self._ddprocess.terminate()
      raise subprocess.CalledProcessError(
          0, self._DD_BINARY, 'CloseStream() called but stdout still had data')

    self._ddprocess.wait()
    code = self._ddprocess.returncode
    error = self._ddprocess.stderr.read()
    if code < 0:
      raise subprocess.CalledProcessError(code, self._DD_BINARY, error)
    return error

  def GetDescription(self):
    """Get a human readable description about the device.

    Returns:
      str: the description
    """
    return 'Name: {0} (Size: {1:d})'.format(self.name, self.size)

  def ProbablyADisk(self):
    """Returns whether this is probably one of the system's internal disks."""
    return True


class MacDiskArtifact(DiskArtifact):
  """The MacDiskArtifact class.

  Attributes:
    hashlog_filename (str): where dcfldd will store the hashes.
    name (str): the name of the artifact.
    remote_path (str): the path to the artifact in the remote storage.
    size (int): the size of the artifact, in bytes.
  """

  # When installed with HomeBrew
  _DD_BINARY = '/usr/local/bin/dcfldd'

  def __init__(self, path, size):
    """Initializes a MacDiskArtifact object.

    Only supported implementations are MacOS and Linux.

    Args:
      path(str): the path to the disk.
      size(str): the size of the disk.

    Raises:
      valueerror: if path is none, doesn't start with '/dev' or size is =< 0.
    """
    super(MacDiskArtifact, self).__init__(path, size)
    self._macdisk = macdisk.Disk(self.name)

  def _IsUsb(self):
    """Whether this device is connected on USB."""
    return self._macdisk.busprotocol == 'USB'

  def ProbablyADisk(self):
    """Returns whether this is probably one of the system's internal disks."""
    if self._IsUsb():
      # We ignore USB to try to avoid copying the GiftStick itself.
      return False
    if self._IsUsb():
      return False
    if self._macdisk.internal and (
        # pylint: disable=protected-access
        self._macdisk._attributes['VirtualOrPhysical'] != 'Virtual'):
      return False
    return True

class LinuxDiskArtifact(DiskArtifact):
  """The DiskArtifact class.

  Attributes:
    hashlog_filename (str): where dcfldd will store the hashes.
    name (str): the name of the artifact.
    remote_path (str): the path to the artifact in the remote storage.
    size (int): the size of the artifact, in bytes.
  """

  def __init__(self, path, size):
    """Initializes a LinuxDiskArtifact object.

    Args:
      path(str): the path to the disk.
      size(str): the size of the disk.

    Raises:
      valueerror: if path is none, doesn't start with '/dev' or size is =< 0.
    """

    super(LinuxDiskArtifact, self).__init__(path, size)

    self._udevadm_metadata = None

  def GetDescription(self):
    """Get a human readable description about the device.

    Returns:
      str: the description
    """
    model = self._GetUdevadmProperty('ID_MODEL')
    if self._IsFloppy():
      model = 'Floppy Disk'
    if not model:
      model = self._GetUdevadmProperty('ID_SERIAL')
    connection = '(internal)'
    if self._IsUsb():
      model = '{0} {1}'.format(self._GetUdevadmProperty('ID_VENDOR'), model)
      connection = '(usb)'
    return '{0}: {1} {2}'.format(self.name, model, connection)

  def _GetUdevadmProperty(self, prop):
    """Get a udevadm property.

    Args:
      prop(str): the property to query.

    Returns:
      str: the value of the property or None if the property is not set.
    """
    if not self._udevadm_metadata:
      self._udevadm_metadata = hostinfo.GetUdevadmInfo(self.name)
    return self._udevadm_metadata.get(prop, None)

  def ProbablyADisk(self):
    """Returns whether this is probably one of the system's internal disks."""
    if self._IsFloppy():
      return False
    if self._IsUsb():
      # We ignore USB to try to avoid copying the GiftStick itself.
      return False
    return True

  def _IsFloppy(self):
    """Whether this block device is a floppy disk."""
    # see https://www.kernel.org/doc/html/latest/admin-guide/devices.html
    return self._GetUdevadmProperty('MAJOR') == '2'

  def _IsUsb(self):
    """Whether this device is connected on USB."""
    return self._GetUdevadmProperty('ID_BUS') == 'usb'


class DiskRecipe(base.BaseRecipe):
  """The DiskRecipe class.

  This Recipe acquires the raw image of all disks on the system.
  """

  def __init__(self, name, options=None):
    """Initializes a DiskRecipe object.

    Args:
      name (str): the name of the artifact.

    Raises:
      ValueError: if the name is empty or None.
    """
    super(DiskRecipe, self).__init__(name, options=options)

  def _GetLsblkDict(self):
    """Calls lsblk.

    Returns:
      dict: the output of the lsblk command.
    """
    lsblk_output = subprocess.check_output(
        ['/bin/lsblk', '-J', '--bytes', '-o', '+UUID,FSTYPE,SERIAL'])
    return json.loads(lsblk_output)

  def _ListAllDisksMac(self):
    """Lists all disks connected to the machine.

    Returns:
      list(MacDiskArtifact): a list of disks.
    """
    disk_list = []
    for mac_disk in macdisk.WholeDisks():
      disk_name = mac_disk.deviceidentifier
      disk_size = mac_disk.totalsize
      disk = MacDiskArtifact(os.path.join('/dev', disk_name), disk_size)
      disk_list.append(disk)
    return disk_list

  def _ListAllDisksLinux(self):
    """Lists all disks connected to the machine.

    Returns:
      list(LinuxDiskArtifact): a list of disks.
    """
    lsblk_dict = self._GetLsblkDict()
    disk_list = []
    for blockdevice in lsblk_dict.get('blockdevices', None):
      if blockdevice.get('type') == 'disk':
        disk_name = blockdevice.get('name')
        disk_size_str = blockdevice.get('size')
        disk_size = int(disk_size_str)
        disk = LinuxDiskArtifact(os.path.join('/dev', disk_name), disk_size)
        disk_list.append(disk)
    return disk_list

  def _ListDisks(self, all_devices=False, names=None):
    """Between all disks connected to the machine, selects the one we want to
    acquired.

    Args:
      all_devices(bool): whether to also list devices that aren't internal to
        the system's (ie: removable media).
      names(list(str)): list of disk names (ie: ['sda', 'sdc']) to acquire.
    Returns:
      list(DiskArtifact): a sorted (and curated) list of disks to acquire.
    """
    disk_list = []
    if self._platform == 'darwin':
      disk_list = self._ListAllDisksMac()
    else:
      disk_list = self._ListAllDisksLinux()

    # We order the list by size, descending.
    disk_list = sorted(disk_list, reverse=True, key=lambda disk: disk.size)
    if names:
      return [disk for disk in disk_list if disk.name in names]
    if not all_devices:
      # We resort to guessing
      return [disk for disk in disk_list if disk.ProbablyADisk()]
    return disk_list

  def _GetListDisksArtifact(self):
    """Generates a StringArtifact containing information about all disks.

    Returns:
      StringArtifact: the artifact.
    """
    if self._platform == 'darwin':
      #pylint: disable=protected-access
      diskutil_artifact = base.StringArtifact(
          'Disks/diskutil.txt', json.dumps(
              [md._attributes for md in macdisk.WholeDisks()]))
      return diskutil_artifact

    lsblk_artifact = base.StringArtifact(
        'Disks/lsblk.txt', json.dumps(self._GetLsblkDict()))
    return lsblk_artifact

  def _GetDiskInfoArtifact(self, disk):
    """Returns an StringArtifact containing information about a disk being
    copied.

    Args:
      disk(DiskArtifact): the disk object to get info from.
    """
    if self._platform == 'darwin':
      # TODO
      return None

    #pylint: disable=protected-access
    udevadm_artifact = base.StringArtifact(
        'Disks/{0:s}.udevadm.txt'.format(disk.name),
        disk._GetUdevadmProperty('udevadm_text_output'))
    return udevadm_artifact

  def GetArtifacts(self):
    """Selects the Artifacts to acquire.

    This tries to return as many Artifacts as possible even if some collection
    raised an exception.

    Returns:
      list(DiskArtifact): the artifacts corresponding to copy.

    Raises:
      errors.RecipeException: when no disk is to be collected.
    """
    artifacts = []
    disks_to_collect = []
    if getattr(self._options, 'select_disks', None):
      all_disks = self._ListDisks(all_devices=True)
      disks_to_collect = gui.AskDiskList(all_disks)
    elif getattr(self._options, 'disk', None):
      disks_to_collect = self._ListDisks(names=self._options.disk)
    else:
      disks_to_collect = self._ListDisks()

    if not disks_to_collect:
      raise errors.RecipeException('No disk to collect')

    disk_list_artifact = self._GetListDisksArtifact()
    artifacts.append(disk_list_artifact)

    for disk in disks_to_collect:

      hashlog_artifact = base.FileArtifact(disk.hashlog_filename)
      hashlog_artifact.remote_path = 'Disks/{0:s}'.format(
          hashlog_artifact.name)

      # It is necessary for the DiskArtifact to be appended before the
      # hashlog, as the hashlog is generated when dcfldd completes.
      disk_info_artifact = self._GetDiskInfoArtifact(disk)
      if disk_info_artifact:
        artifacts.append(disk_info_artifact)
      artifacts.append(disk)
      artifacts.append(hashlog_artifact)
    return artifacts
