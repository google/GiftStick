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

    Args:
      path(str): the path to the disk.
      size(str): the size of the disk.

    Raises:
      ValueError: if path is None, doesn't start with '/dev' or size is =< 0.
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

    self._udevadm_metadata = None

  def __cmp__(self, other):
    return cmp(self.size, other.size)

  def __lt__(self, other):
    return self.size < other.size

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
    if c != '':  # pylint: disable=g-explicit-bool-comparison
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
    return self.GetUdevadmProperty('MAJOR') == '2'

  def _IsUsb(self):
    """Whether this device is connected on USB."""
    return self.GetUdevadmProperty('ID_BUS') == 'usb'

  def GetDescription(self):
    """Get a human readable description about the device.

    Returns:
      str: the description
    """
    model = self.GetUdevadmProperty('ID_MODEL')
    if self._IsFloppy():
      model = 'Floppy Disk'
    if not model:
      model = self.GetUdevadmProperty('ID_SERIAL')
    connection = '(internal)'
    if self._IsUsb():
      model = '{0} {1}'.format(self.GetUdevadmProperty('ID_VENDOR'), model)
      connection = '(usb)'
    return '{0}: {1} {2}'.format(self.name, model, connection)

  def GetUdevadmProperty(self, prop):
    """Get a udevadm property.

    Args:
      prop(str): the property to query.

    Returns:
      str: the value of the property or None if the property is not set.
    """
    if not self._udevadm_metadata:
      self._udevadm_metadata = hostinfo.GetUdevadmInfo(self.name)
    return self._udevadm_metadata.get(prop, None)


class DiskRecipe(base.BaseRecipe):
  """The DiskRecipe class.

  This Recipe acquires the raw image of all disks on the system.
  """

  def _GetLsblkDict(self):
    """Calls lsblk.

    Returns:
      dict: the output of the lsblk command.
    """
    lsblk_output = subprocess.check_output(
        ['/bin/lsblk', '-J', '--bytes', '-o', '+UUID,FSTYPE,SERIAL'])
    return json.loads(lsblk_output)

  def _ListDisks(self, all_devices=False):
    """Lists disks connected to the machine.

    Args:
      all_devices(bool): whether to also list devices that aren't internal to
      the system's (ie: removable media).

    Returns:
      list(DiskArtifact): a list of disks.

    Raises:
      errors.RecipeException: when no disk could be detected.
    """
    lsblk_dict = self._GetLsblkDict()
    disk_list = []
    for blockdevice in lsblk_dict.get('blockdevices', None):
      if blockdevice.get('type') == 'disk':
        disk_name = blockdevice.get('name')
        disk_size_str = blockdevice.get('size')
        disk_size = int(disk_size_str)
        disk = DiskArtifact(os.path.join('/dev', disk_name), disk_size)
        if all_devices or disk.ProbablyADisk():
          disk_list.append(disk)
    # We order the list by size, descending.
    return sorted(disk_list, reverse=True)

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
    else:
      disks_to_collect = self._ListDisks()

    if not disks_to_collect:
      raise errors.RecipeException('No disk to collect')

    lsblk_artifact = base.StringArtifact(
        'Disks/lsblk.txt', json.dumps(self._GetLsblkDict()))
    for disk in disks_to_collect:
      udevadm_artifact = base.StringArtifact(
          'Disks/{0:s}.udevadm.txt'.format(disk.name),
          disk.GetUdevadmProperty('udevadm_text_output'))

      hashlog_artifact = base.FileArtifact(disk.hashlog_filename)
      hashlog_artifact.remote_path = 'Disks/{0:s}'.format(
          hashlog_artifact.name)

      # It is necessary for the DiskArtifact to be appended before the
      # hashlog, as the hashlog is generated when dcfldd completes.
      artifacts.append(udevadm_artifact)
      artifacts.append(lsblk_artifact)
      artifacts.append(disk)
      artifacts.append(hashlog_artifact)
    return artifacts

