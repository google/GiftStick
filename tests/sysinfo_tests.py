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

import mock


# pylint: disable=missing-docstring
class LinuxSysinfoRecipeTest(unittest.TestCase):
  """Tests for the SysinfoRecipe class."""

  _DMIDECODE_OUTPUT_FAIL_STRING = (
      b'/dev/mem: Permission denied\n Error running dmidecode')

  _DMIDECODE_OUTPUT_STRING = b"""\
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
    # pylint: disable=protected-access
    sysinfo_recipe._platform = 'linux'
    # pylint: disable=line-too-long
    with mock.patch('auto_forensicate.recipes.base.ProcessOutputArtifact._RunCommand') as patched_run:
      patched_run.return_value = self._DMIDECODE_OUTPUT_FAIL_STRING
      artifacts = sysinfo_recipe.GetArtifacts()
      self.assertEqual(len(artifacts), 2)

      artifact = artifacts[0]
      self.assertIsInstance(artifact, base.ProcessOutputArtifact)
      self.assertEqual(artifact.name, 'system_info.txt')
      self.assertEqual(artifact.remote_path, 'system_info.txt')
      artifact_content = artifact.OpenStream().read()
      self.assertEqual(artifact_content, self._DMIDECODE_OUTPUT_FAIL_STRING)

  def testGetArtifacts(self):
    sysinfo_recipe = sysinfo.SysinfoRecipe('sysinfo')
    # pylint: disable=protected-access
    sysinfo_recipe._platform = 'linux'
    # pylint: disable=line-too-long
    with mock.patch('auto_forensicate.recipes.base.ProcessOutputArtifact._RunCommand') as patched_run:
      patched_run.return_value = self._DMIDECODE_OUTPUT_STRING
      artifacts = sysinfo_recipe.GetArtifacts()
      self.assertEqual(len(artifacts), 2)

      artifact = artifacts[0]
      self.assertIsInstance(artifact, base.ProcessOutputArtifact)
      self.assertEqual(artifact.name, 'system_info.txt')
      self.assertEqual(artifact.remote_path, 'system_info.txt')
      artifact_content = artifact.OpenStream().read()
      self.assertEqual(artifact_content, self._DMIDECODE_OUTPUT_STRING)


class MacSysinfoRecipeTest(unittest.TestCase):
  """Tests for the SysinfoRecipe class."""

  _SYSTEM_PROFILER_FAIL_STRING = (
      b'/dev/mem: Permission denied\n Error running dmidecode')

  _SYSTEM_PROFILER_OUTPUT_STRING = b"""\
Hardware:

    Hardware Overview:

      Model Name: MacBook Pro
      Model Identifier: MacBookPro14,3
      Processor Name: Intel Core i7
      Processor Speed: 2.8 GHz
      Number of Processors: 1
      Total Number of Cores: 4
      L2 Cache (per Core): 256 KB
      L3 Cache: 6 MB
      Memory: 16 GB
      Boot ROM Version: 185.0.0.0.0
      SMC Version (system): 2.45f0
      Serial Number (system): CAAAAAAAAAAA
      Hardware UUID: 12345678-E004-5158-AAA-BBBBB52F3949

Software:

    System Software Overview:

      System Version: macOS 10.14.3 (18D42)
      Kernel Version: Darwin 18.2.0
      Boot Volume: Macintosh HD
      Boot Mode: Normal
      Computer Name: macbookpro2
      User Name: Someone Else (someoneelse)
      Secure Virtual Memory: Enabled
      System Integrity Protection: Enabled
      Time since boot: 4 days 3:38
    """

  def testGetArtifactsFail(self):
    sysinfo_recipe = sysinfo.SysinfoRecipe('failsysinfo')
    # pylint: disable=protected-access
    sysinfo_recipe._platform = 'darwin'
    # pylint: disable=line-too-long
    with mock.patch('auto_forensicate.recipes.base.ProcessOutputArtifact._RunCommand') as patched_run:
      patched_run.return_value = self._SYSTEM_PROFILER_FAIL_STRING
      artifacts = sysinfo_recipe.GetArtifacts()
      self.assertEqual(len(artifacts), 2)

      artifact = artifacts[0]
      self.assertIsInstance(artifact, base.ProcessOutputArtifact)
      self.assertEqual(artifact.name, 'system_info.txt')
      self.assertEqual(artifact.remote_path, 'system_info.txt')
      artifact_content = artifact.OpenStream().read()
      self.assertEqual(artifact_content, self._SYSTEM_PROFILER_FAIL_STRING)

  def testGetArtifacts(self):
    sysinfo_recipe = sysinfo.SysinfoRecipe('sysinfo')
    # pylint: disable=protected-access
    sysinfo_recipe._platform = 'darwin'
    # pylint: disable=line-too-long
    with mock.patch('auto_forensicate.recipes.base.ProcessOutputArtifact._RunCommand') as patched_run:
      patched_run.return_value = self._SYSTEM_PROFILER_OUTPUT_STRING
      artifacts = sysinfo_recipe.GetArtifacts()
      self.assertEqual(len(artifacts), 2)

      artifact = artifacts[0]
      self.assertIsInstance(artifact, base.ProcessOutputArtifact)
      self.assertEqual(artifact.name, 'system_info.txt')
      self.assertEqual(artifact.remote_path, 'system_info.txt')
      artifact_content = artifact.OpenStream().read()
      self.assertEqual(artifact_content, self._SYSTEM_PROFILER_OUTPUT_STRING)
