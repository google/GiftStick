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
"""Tests for the base.py module."""

from __future__ import unicode_literals

import os
import tempfile
import unittest
from auto_forensicate.recipes import base
import mock


class BaseArtifactTests(unittest.TestCase):
  """Tests for the BaseArtifact class."""

  def testInstantiate(self):
    artifact_name = 'artifact'
    artifact = base.BaseArtifact(artifact_name)

    self.assertEqual(artifact.size, 0)
    self.assertEqual(artifact.name, artifact_name)
    expected_remote_path = 'Base/artifact'
    self.assertEqual(artifact.remote_path, expected_remote_path)

  def testReadableSize(self):
    artifact_name = 'artifact'
    artifact = base.BaseArtifact(artifact_name)
    self.assertEqual(artifact.readable_size, 'Unknown size')

    artifact._size = 12345
    self.assertEqual(artifact.readable_size, '12.1KiB')

    artifact._size = 1234567
    self.assertEqual(artifact.readable_size, '1.2MiB')

    artifact._size = 123456789
    self.assertEqual(artifact.readable_size, '117.7MiB')

    artifact._size = 12345678901
    self.assertEqual(artifact.readable_size, '11.5GiB')

    artifact._size = 1023 * 1024 * 1024 * 1024
    self.assertEqual(artifact.readable_size, '1,023.0GiB')

    artifact._size = 1234567890123
    self.assertEqual(artifact.readable_size, '1.1TiB')

    artifact._size = 12345678901234567890
    self.assertEqual(artifact.readable_size, '10,965.2PiB')

  def testOpenStream(self):
    artifact = base.BaseArtifact('artifact')
    with self.assertRaises(NotImplementedError) as err:
      artifact.OpenStream()
    expected_err_message = '_GetStream() is not implemented in BaseArtifact'
    self.assertEqual(str(err.exception), expected_err_message)


class ProcessOutputArtifactTest(unittest.TestCase):
  """Tests for the ProcessOutputArtifact class."""

  _TEST_OUTPUT = b'this is some command output'

  def testRunCommand(self):
    cmd = ['echo', '-n', self._TEST_OUTPUT]
    artifact = base.ProcessOutputArtifact(cmd, 'output.txt')

    self.assertEqual(artifact._command, cmd)
    self.assertEqual(artifact.name, 'output.txt')
    # Size is unknown until the command is run
    self.assertEqual(artifact.size, 0)

    artifact_content = artifact.OpenStream().read()
    self.assertEqual(artifact.size, 27)

    self.assertEqual(artifact_content, self._TEST_OUTPUT)


class BaseRecipeTests(unittest.TestCase):
  """Tests for the BaseRecipe class."""

  def setUp(self):
    self.temp_directory = tempfile.mkdtemp()

  def testContextManager(self):
    with mock.patch('tempfile.mkdtemp', lambda: self.temp_directory):
      with base.BaseRecipe('fake_recipe') as recipe:
        self.assertTrue(os.path.isdir(self.temp_directory))
        self.assertEqual(recipe._workdir, self.temp_directory)
      self.assertFalse(os.path.isdir(self.temp_directory))
