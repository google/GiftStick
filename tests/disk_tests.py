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

import json
import unittest
from auto_forensicate import errors
from auto_forensicate.recipes import base
from auto_forensicate.recipes import disk
import mock


# pylint: disable=missing-docstring
# pylint: disable=protected-access

class DiskArtifactTests(unittest.TestCase):
  """Tests for the DiskArtifact class."""

  def testInstantiate(self):
    name = 'sdx'
    path = '/dev/{0:s}'.format(name)
    d = disk.DiskArtifact(path, 100)
    self.assertEqual(d._path, path)
    self.assertEqual(d.name, name)
    self.assertEqual(d.remote_path, 'Disks/{0:s}.image'.format(name))
    self.assertEqual(d.hashlog_filename, '{0:s}.hash'.format(name))

  def testGenerateDDCommand(self):
    name = 'sdx'
    path = '/dev/{0:s}'.format(name)
    dd_command = [
        '/usr/bin/dcfldd', 'if={0:s}'.format(path),
        'hashlog={0:s}.hash'.format(name)]
    dd_static_options = [
        'hash=md5,sha1', 'bs=2M', 'conv=noerror', 'hashwindow=128M']
    dd_command.extend(dd_static_options)

    d = disk.DiskArtifact(path, 100)
    self.assertEqual(d._GenerateDDCommand(), dd_command)

  def testIsFloppy(self):
    disk_object = disk.DiskArtifact('/dev/sdX', 12345)
    disk_object._udevadm_metadata = {'MAJOR': '2'}
    self.assertTrue(disk_object._IsFloppy())
    disk_object._udevadm_metadata = {'MAJOR': '12'}
    self.assertFalse(disk_object._IsFloppy())

  def testIsUsb(self):
    disk_object = disk.DiskArtifact('/dev/sdX', 12345)
    disk_object._udevadm_metadata = {'ID_BUS': 'usb'}
    self.assertTrue(disk_object._IsUsb())
    disk_object._udevadm_metadata = {'ID_BUS': 'ata'}
    self.assertFalse(disk_object._IsUsb())

  def testProbablyADisk(self):
    disk_object = disk.DiskArtifact('/dev/sdX', 123456789)
    disk_object._udevadm_metadata = {'ID_BUS': 'ata'}
    self.assertTrue(disk_object.ProbablyADisk())

    # We ignore USB to try to avoid copying the GiftStick itself.
    disk_object._udevadm_metadata = {'ID_BUS': 'usb'}
    self.assertFalse(disk_object.ProbablyADisk())

    # We ignore Floppy
    disk_object._udevadm_metadata = {'MAJOR': '2'}
    self.assertFalse(disk_object.ProbablyADisk())

    # Fancy NVME drive
    disk_object._udevadm_metadata = {
        'DEVTYPE': 'disk',
        'MAJOR': '259',
        'MINOR': '0'
    }
    self.assertTrue(disk_object.ProbablyADisk())

  def testGetDescription(self):
    disk_object = disk.DiskArtifact('/dev/sdX', 123456789)
    disk_object._udevadm_metadata = {
        'ID_BUS': 'ata',
        'ID_MODEL': 'TestDisk'
    }
    self.assertEqual('sdX: TestDisk (internal)', disk_object.GetDescription())

    disk_object._udevadm_metadata = {
        'ID_BUS': 'usb',
        'ID_MODEL': 'TestDisk',
        'ID_VENDOR': 'FakeVendor'
    }
    self.assertEqual(
        'sdX: FakeVendor TestDisk (usb)', disk_object.GetDescription())

    disk_object._udevadm_metadata = {
        'MAJOR': '2',
    }
    self.assertEqual(
        'sdX: Floppy Disk (internal)', disk_object.GetDescription())


class DiskRecipeTests(unittest.TestCase):
  """Tests for the DiskRecipe class."""

  def setUp(self):
    self._lsblk_dict = {
        'blockdevices': [
            {'name': 'loop0', 'maj:min': '7:0', 'rm': '0', 'size': '1073741824',
             'ro': '1', 'type': 'loop', 'mountpoint': '/dev/loop0', 'uuid': None
            },
            {'name': 'sdx', 'maj:min': '8:0', 'rm': '0', 'size': '502110190592',
             'ro': '0', 'type': 'disk', 'mountpoint': None,
             'children': [
                 {'name': 'sdx1', 'maj:min': '8:1', 'rm': '0',
                  'size': '48725121', 'ro': '0', 'type': 'part',
                  'mountpoint': '/boot', 'uuid': 'fake_uuid_1'},
                 {'name': 'sdx2', 'maj:min': '8:2', 'rm': '0', 'size': '231201',
                  'ro': '0', 'type': 'part', 'mountpoint': None,
                  'uuid': 'fake_uuid_2'},
             ]
            },
            {'name': 'usb0', 'maj:min': '8:16', 'rm': '1', 'size': '3000041824',
             'ro': '0', 'type': 'disk', 'mountpoint': None, 'uuid': None
            },
            {'name': 'sdy', 'maj:min': '8:0', 'rm': '0', 'size': '512110190592',
             'ro': '0', 'type': 'disk', 'mountpoint': None, 'uuid': None,
             'children': [
                 {'name': 'sdy1', 'maj:min': '8:1', 'rm': '0',
                  'size': '48725121', 'ro': '0', 'type': 'part',
                  'mountpoint': '/boot', 'uuid': None},
             ]
            }
        ]
    }

  def _GetLsblkDictZeroDisks(self):
    return {'blockdevices': []}

  def _GetLsblkDictThreeDisks(self):
    return self._lsblk_dict

  def testListDisksZero(self):
    recipe = disk.DiskRecipe('Disk')
    disk.DiskRecipe._GetLsblkDict = self._GetLsblkDictZeroDisks
    self.assertEqual(0, len(recipe._ListDisks()))

  def testListAllDisks(self):
    recipe = disk.DiskRecipe('Disk')
    disk.DiskRecipe._GetLsblkDict = self._GetLsblkDictThreeDisks
    disk_list = recipe._ListDisks(all_devices=True)
    self.assertEqual(len(disk_list), 3)
    self.assertGreaterEqual(disk_list[0].size, disk_list[1].size)
    self.assertEqual(disk_list[0].size, 512110190592)
    self.assertEqual(disk_list[1].size, 502110190592)
    self.assertEqual(disk_list[2].size, 3000041824)

  def testGetArtifactsZeroDisk(self):
    with mock.patch(
        'auto_forensicate.recipes.disk.DiskRecipe._ListDisks'
    ) as patched_listdisk:
      patched_listdisk.return_value = []
      recipe = disk.DiskRecipe('Disk')
      with self.assertRaises(errors.RecipeException):
        recipe.GetArtifacts()

  def testGetArtifacts(self):
    disk_name = 'sdx'
    disk_size = 20 * 1024 * 1024 * 1024  # 20GB
    disk_object = disk.DiskArtifact('/dev/{0:s}'.format(disk_name), disk_size)
    disk_object._udevadm_metadata = {'udevadm_text_output': 'fake disk info'}
    with mock.patch(
        'auto_forensicate.recipes.disk.DiskRecipe._ListDisks'
    ) as patched_listdisk:
      patched_listdisk.return_value = [disk_object]
      with mock.patch(
          'auto_forensicate.recipes.disk.DiskRecipe._GetLsblkDict'
      ) as patched_lsblk:
        patched_lsblk.return_value = self._lsblk_dict
        recipe = disk.DiskRecipe('Disk')
        artifacts = recipe.GetArtifacts()
        self.assertEqual(len(artifacts), 4)

        udevadm_artifact = artifacts[0]
        self.assertIsInstance(udevadm_artifact, base.StringArtifact)
        self.assertEqual(udevadm_artifact._GetStream().read(), b'fake disk info')
        self.assertEqual(udevadm_artifact.remote_path, 'Disks/sdx.udevadm.txt')

        lsblk_artifact = artifacts[1]
        self.assertIsInstance(lsblk_artifact, base.StringArtifact)
        self.assertEqual(
            lsblk_artifact._GetStream().read(), json.dumps(self._lsblk_dict).encode('utf-8'))
        self.assertEqual(lsblk_artifact.remote_path, 'Disks/lsblk.txt')

        self.assertEqual(artifacts[2], disk_object)

        file_artifact = artifacts[3]
        self.assertIsInstance(file_artifact, base.FileArtifact)
        self.assertEqual(file_artifact.name, '{0:s}.hash'.format(disk_name))
        self.assertEqual(
            file_artifact.remote_path, 'Disks/{0:s}.hash'.format(disk_name))
