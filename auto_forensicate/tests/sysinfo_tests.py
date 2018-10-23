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
"""Tests for the sysinfo.py recipe module."""

from __future__ import unicode_literals

import unittest
from auto_forensicate.recipes import base
from auto_forensicate.recipes import sysinfo


class SysinfoRecipeTest(unittest.TestCase):
  """Tests for the SysinfoRecipe class."""

  _DMIDECODE_OUTPUT_FAIL_STRING = (
      '/dev/mem: Permission denied\n Error running dmidecode')

  _DMIDECODE_OUTPUT_STRING = """\
    # dmidecode 2.12
    SMBIOS 2.8 present.

    Handle 0x0001, DMI type 1, 27 bytes
    System Information
	    Manufacturer: Cyber Computers Inc
	    Product Name: The Great Workstation
	    Version: Not Specified
	    Serial Number: CAAAAAAA
	    UUID: A419F8CA-1234-0000-9C43-BC0000D00000
	    Wake-up Type
	    SKU Number: 1231456#ABU
	    Family: 103C_55555X G=D
    """

  def testGetArtifactsFail(self):
    sysinfo_recipe = sysinfo.SysinfoRecipe('failsysinfo')
    sysinfo_recipe._DMI_DECODE_CMD = [
        'echo', '-n', self._DMIDECODE_OUTPUT_FAIL_STRING]
    artifacts = sysinfo_recipe.GetArtifacts()
    self.assertEqual(len(artifacts), 1)

    artifact = artifacts[0]
    self.assertIsInstance(artifact, base.ProcessOutputArtifact)
    self.assertEqual(artifact.name, 'system_info.txt')
    self.assertEqual(artifact.remote_path, 'system_info.txt')
    artifact_content = artifact.OpenStream().read()
    self.assertEqual(artifact_content, self._DMIDECODE_OUTPUT_FAIL_STRING)

  def testGetArtifacts(self):
    sysinfo_recipe = sysinfo.SysinfoRecipe('sysinfo')
    sysinfo_recipe._DMI_DECODE_CMD = [
        'echo', '-n', self._DMIDECODE_OUTPUT_STRING]
    artifacts = sysinfo_recipe.GetArtifacts()
    self.assertEqual(len(artifacts), 1)

    artifact = artifacts[0]
    self.assertIsInstance(artifact, base.ProcessOutputArtifact)
    self.assertEqual(artifact.name, 'system_info.txt')
    self.assertEqual(artifact.remote_path, 'system_info.txt')
    artifact_content = artifact.OpenStream().read()
    self.assertEqual(artifact_content, self._DMIDECODE_OUTPUT_STRING)
