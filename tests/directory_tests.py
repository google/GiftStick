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
"""Tests for the disk.py module."""

from __future__ import unicode_literals

import os
import subprocess
import tempfile
import unittest
from auto_forensicate.recipes import directory

# pylint: disable=missing-docstring
# pylint: disable=protected-access


class DirectoryArtifactTests(unittest.TestCase):
  """Tests for the DirectoryArtifact class."""

  def _EmptyFolderSize(self):
    """Returns the size of an empty folder.

    This should match the current filesystem blocksize.
    """
    size = int(subprocess.check_output(['stat', '-fc', '%s', '.']).strip())
    return size

  def testInstantiate(self):
    with tempfile.TemporaryDirectory() as path:
      expected_name = path.replace(os.path.sep, '_')
      d = directory.DirectoryArtifact(path, method='tar', compress=False)
      self.assertEqual(d.path, path)
      self.assertEqual(d.name, expected_name)
      self.assertEqual(
          d.remote_path, 'Directories/{0:s}.tar'.format(expected_name))
      self.assertEqual(d.size, self._EmptyFolderSize())

      d = directory.DirectoryArtifact(path, method='tar', compress=True)
      self.assertEqual(
          d.remote_path, 'Directories/{0:s}.tar.gz'.format(expected_name))

  def testGenerateTarCopyCommand(self):
    with tempfile.TemporaryDirectory() as path:
      d = directory.DirectoryArtifact(path, method='tar', compress=False)
      command = d._TAR_COMMAND
      command.append(path)
      self.assertEqual(d._GenerateCopyCommand(), command)

  def testGenerateTarGzCopyCommand(self):
    with tempfile.TemporaryDirectory() as path:
      d = directory.DirectoryArtifact(path, method='tar', compress=True)
      command = d._TAR_COMMAND
      command.append('-z')
      command.append(path)
      self.assertEqual(d._GenerateCopyCommand(), command)
