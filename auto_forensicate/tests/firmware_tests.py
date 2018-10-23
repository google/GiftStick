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
"""Tests for the firmware.py module."""

from __future__ import unicode_literals

import unittest
from auto_forensicate.recipes import base
from auto_forensicate.recipes import firmware


class ChipsecRecipeTests(unittest.TestCase):
  """Tests for the ChipsecRecipe class."""

  _CHIPSEC_OUTPUT_STRING = b'\xff' * 256

  def testGetArtifacts(self):
    chipsec_recipe = firmware.ChipsecRecipe('chipsec')
    chipsec_recipe._CHIPSEC_CMD = [
        'echo', '-n', self._CHIPSEC_OUTPUT_STRING]

    artifacts = chipsec_recipe.GetArtifacts()
    self.assertEqual(len(artifacts), 1)

    artifact = artifacts[0]
    self.assertIsInstance(artifact, base.ProcessOutputArtifact)
    self.assertEqual(artifact.name, 'rom.bin')
    self.assertEqual(artifact.remote_path, 'Firmware/rom.bin')
    artifact_content = artifact.OpenStream().read()
    self.assertEqual(artifact_content, self._CHIPSEC_OUTPUT_STRING)
