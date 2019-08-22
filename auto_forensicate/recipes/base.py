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
"""Base classes for Artifacts and Recipes."""

from __future__ import unicode_literals

import logging
import os
from io import BytesIO
import shutil
import subprocess
import sys
import tempfile
import six


class BaseArtifact(object):
  """BaseArtifact class.

  Attributes:
    logger (Logger): a Logger object.
    name (str): the name of the artifact.
    remote_path (str): the path to the artifact in the remote storage.
    size (int): the size of the artifact, in bytes.
  """

  def __init__(self, name):
    """Initializes a BaseArtifact object.

    Args:
      name (str): the name of the artifact.

    Raises:
      ValueError: if the name is empty or None.
    """
    self._size = 0
    self._stream = None
    if name:
      self.name = name
    else:
      raise ValueError('The name of the artifact must not be None or empty.')
    self.remote_path = 'Base/{0:s}'.format(self.name)

    self._logger = logging.getLogger(self.__class__.__name__)

  def _GetStream(self):
    """Get access to the file-like object.

    Raises:
      NotImplementedError: If this method is not implemented.
    """
    class_name = type(self).__name__
    raise NotImplementedError(
        '_GetStream() is not implemented in {0:s}'.format(class_name))

  def CloseStream(self):
    """Closes the file-like object.

    Raises:
      IOError: if this method is called before OpenStream.
    """
    if self._stream:
      self._logger.debug('Closing stream')
      self._stream.close()
    else:
      raise IOError('Illegal call to CloseStream() before OpenStream()')

  def OpenStream(self):
    """Get the file-like object to the data of the artifact.

    Returns:
      file: Read-only file-like object to the data.
    """
    self._logger.debug('Opening stream')
    if not self._stream:
      # pylint: disable=assignment-from-no-return
      self._stream = self._GetStream()

    return self._stream

  @property
  def size(self):
    """The size of the artifact.

    Returns:
      int: the size of the artifact in bytes.
    """
    return self._size

  @property
  def readable_size(self):
    """The size of the artifact, in human readable form.

    Returns:
      str: the size of the artifact in human readable form.
    """
    current_size = self._size
    if current_size == 0:
      return 'Unknown size'
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
      if abs(current_size) < 1024:
        return '{0:3,.1f}{1:s}'.format(current_size, unit)
      current_size /= 1024.0
    return '{0:,.1f}{1:s}'.format(current_size, 'PiB')


class StringArtifact(BaseArtifact):
  """Class for an artifact that uploads a string to a file."""

  def __init__(self, path, string_content):
    """Initializes a StringArtifact object.

    Args:
      path (str): the path to the artifact in the remote storage.
      string_content (str): the string to upload.

    Raises:
      ValueError: if the path doesn't point to a file.
    """
    super(StringArtifact, self).__init__(os.path.basename(path))
    if isinstance(string_content, six.text_type):
      self._data = string_content.encode('utf-8')
    else:
      self._data = string_content
    self._size = len(self._data)
    self.remote_path = path
    self._stream = None

  def _GetStream(self):
    """Get access to the file-like object."""
    if self._stream is None:
      self._stream = BytesIO(self._data)
    return self._stream

  def CloseStream(self):
    if self._stream is None:
      raise IOError('Should not call CloseStream() before GetStream()')
    self._stream.close()


class FileArtifact(BaseArtifact):
  """Class for an artifact to upload a File."""

  def __init__(self, path):
    """Initializes a FileArtifact object.

    Args:
      path (str): the absolute, or relative to the recipe's temporary, path to
        the file.

    Raises:
      ValueError: if the path doesn't point to a file.
    """
    super(FileArtifact, self).__init__(os.path.basename(path))
    self._path = path

    if os.path.isfile(path):
      self._size = os.stat(path).st_size
    self.remote_path = 'Files/{0:s}'.format(self.name)

  def _GetStream(self):
    """Get the file-like object to the data of the artifact.

    Returns:
      file: Read-only file-like object to the data.
    """
    return open(os.path.realpath(self._path), 'rb')


class ProcessOutputArtifact(BaseArtifact):
  """Class for an artifact to upload the output of a command."""

  def __init__(self, command, path):
    """Initializes a ProcessOutputArtifact object.

    Args:
      command (list): the command to run as subprocess.
      path (str): the remote path to store the output of the command.
    """
    super(ProcessOutputArtifact, self).__init__(os.path.basename(path))
    self.remote_path = path
    self._buffered_content = None
    self._command = command

  def _RunCommand(self):
    """Run a command.

    Returns:
      str: the command output, or an error if it failed to run.
    """
    command_output = ''
    process = subprocess.Popen(
        self._command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self._logger.info('Running command \'%s\'', self._command)
    output, error = process.communicate()

    if process.returncode == 0:
      command_output = output
      self._logger.info('Command %s terminated.', self._command)
      self._logger.debug('stderr : \'%s\'', error.strip())
    else:
      command_output = (
          'Command \'{0:s}\' failed with \'{1:s}\' return code {2:d})'.format(
              self._command, error.strip(), process.returncode))
      self._logger.error(command_output)
      command_output = command_output.decode('utf-8', 'ignore')

    return command_output

  def _GetStream(self):
    """Get the file-like object to the data of the artifact.

    Returns:
      file: Read-only file-like object to the data.
    """
    if not self._buffered_content:
      command_output = self._RunCommand()
      self._size = len(command_output)
      self._buffered_content = BytesIO(command_output)
    return self._buffered_content


class BaseRecipe(object):
  """BaseRecipe class."""

  def __init__(self, name, options=None):
    """Initializes a BaseRecipe object.

    Args:
      name(str): the name of the Recipe.
      options(argparse.Namespace): options parsed from the command line.

    Raises:
      ValueError: if the name parameter is None.
    """
    self._platform = sys.platform
    self._workdir = None
    if name:
      self.name = name
    else:
      raise ValueError('A Recipe needs a name')
    self._options = options
    self._origin_dir = os.getcwd()

    self._logger = logging.getLogger(self.__class__.__name__)

  def __enter__(self):
    self._workdir = tempfile.mkdtemp()
    os.chdir(self._workdir)
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    os.chdir(self._origin_dir)
    shutil.rmtree(self._workdir)

  def GetArtifacts(self):
    """Provides a list of Artifacts to upload.

    Returns:
      list(BaseArtifact): the artifacts to copy.
    """
    return list()
