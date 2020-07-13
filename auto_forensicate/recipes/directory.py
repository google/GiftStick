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
"""Handles the acquisition of the directories."""

import os
import subprocess

from auto_forensicate import errors
from auto_forensicate.recipes import base
from auto_forensicate.ux import cli
from auto_forensicate.ux import gui


class DirectoryArtifact(base.BaseArtifact):
  """The DirectoryArtifact class.

  Attributes:
    name (str): the name of the artifact.
    remote_path (str): the path to the artifact in the remote storage.
    size (int): the size of the artifact, in bytes.
  """

  _SUPPORTED_METHODS = ['tar']

  def __init__(self, path, method='tar', compress=False):
    """Initializes a DirectoryArtifact object.

    Args:
      path(str): the path to the directory.
      method(str): the method used for acquisition.
      compress(bool): whether to use compression (not supported by all methods).

    Raises:
      ValueError: if path is none, or doesn't exist
    """
    super(DirectoryArtifact, self).__init__(os.path.basename(path))
    if not os.path.exists(path):
      raise ValueError(
          'Error with path {0:s} does not exist'.format(path))

    self.path = path
    self._size = self._GetSize()
    self._copy_command = None
    self._method = method
    self._compress = compress
    if self._method == 'tar':
      self.remote_path = 'Directories/{0:s}.tar'.format(self.name)

    if self._compress:
      self.remote_path = self.remote_path + '.gz'

  def _GetSize(self):
    """TODO."""
    du_process = subprocess.run(
        ['du', '-s', '-b', self.path], stdout=subprocess.PIPE, check=False)
    du_output = int(du_process.stdout.split()[0])
    return du_output

  def _GetStream(self):
    """Get the file-like object to the data of the artifact.

    Returns:
      file: Read-only file-like object to the data.

    Raises:
      IOError: If this method is called more than once before CloseStream().
    """
    if self._copy_command is None:
      self._copy_command = self._GenerateCopyCommand()
    self._logger.info(
        'Copying directory with command \'{0!s}\''.format(self._copy_command))
    self._copyprocess = subprocess.Popen(
        self._copy_command, stdin=None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return self._copyprocess.stdout

  def CloseStream(self):
    """Closes the file-like object.

    Returns:
      str: a return message for the report.

    Raises:
      subprocess.CalledProcessError: if the copy process returns with an error.
      IOError: if CloseStream() is called before GetStream().
    """
    if not self._copyprocess:
      raise IOError('Illegal call to CloseStream() before GetStream()')

    # If there is anything still to read from the subprocess then CloseStream
    # has been called early, terminate the child process to avoid deadlock.
    c = self._copyprocess.stdout.read(1)
    if c:
      # TODO log this
      self._copyprocess.terminate()
      raise subprocess.CalledProcessError(
          0, self._copy_command[0],
          'CloseStream() called but stdout still had data')

    self._copyprocess.wait()
    code = self._copyprocess.returncode
    error = self._copyprocess.stderr.read()
    if code < 0:
      raise subprocess.CalledProcessError(code, self._copy_command[0], error)
    return error

  def _GenerateCopyCommand(self):
    if self._method == 'tar':
      return self._GenerateTarCopyCommand()
    else:
      raise errors.RecipeException('Unsupported method '+self._method)

#  def _GenerateTarCopyCommand(self):
#    raise RuntimeError('_GenerateTarCopyCommand not implemented')

  def _GenerateTarCopyCommand(self):
    """TODO"""

    command = ['sudo', 'tar', '-c', '-O', '-p', '--xattrs', '--acls', '--atime-preserve=system', '--format=posix']
    if self._compress:
      command.append('-z')

    command.append(self.path)

    return command


class LinuxDirectoryArtifact(DirectoryArtifact):
  """The LinuxDirectoryArtifact class."""

  def __init__(self, path, method='tar', compress=False):
    """TODO"""
    super().__init__(path, method=method, compress=compress)
    if method not in self._SUPPORTED_METHODS:
      raise errors.RecipeException(
          'Unsupported acquisition method on Linux: '+method)


class MacDirectoryArtifact(DirectoryArtifact):
  """The MacDirectoryArtifact class."""

  def __init__(self, path, method='tar', compress=False):
    """TODO"""
    if method not in self._SUPPORTED_METHODS:
      raise errors.RecipeException(
          'Unsupported acquisition method on Darwin: '+method)

    super(MacDirectoryArtifact, self).__init__(
        path, method=method, compress=compress)


class DirectoryRecipe(base.BaseRecipe):
  """The DirectoryRecipe class.

  This Recipe acquires a mounted filesystem.
  """

  def GetArtifacts(self):
    """Returns a list of DirectoryArtifacts to acquire.

    Returns:
      list(DirectoryArtifacts): the artifacts to acquire.
    """
    more_to_copy = True
    path_list = []
    while more_to_copy:
      if getattr(self._options, 'no_zenity', False):
        path = cli.AskText(
            'Specify the path to the directory you wish to copy')
        if not os.path.isdir(path):
          continue
        path_list.append(path)
        more_to_copy = cli.Confirm('Do you wish to copy another folder?')
      else:
        path = gui.AskText(
            'Specify the path to the directory you wish to copy')
        if not os.path.isdir(path):
          continue
        path_list.append(path)
        more_to_copy = gui.Confirm('Do you wish to copy another folder?')

    if not path_list:
      raise errors.RecipeException('No directory to collect')

    artifacts = []
    for directory in path_list:
      if self._platform == 'darwin':
        artifacts.append(MacDirectoryArtifact(directory))
      elif self._platform == 'linux':
        artifacts.append(LinuxDirectoryArtifact(directory))
      else:
        raise ValueError('Unsupported platform: {0:s}'.self._platform)

    return artifacts


