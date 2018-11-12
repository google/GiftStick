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
"""Tests for the utils module."""

from __future__ import unicode_literals

import unittest
import uuid
from auto_forensicate import hostinfo
import mock


class HostInfoTests(unittest.TestCase):
  """Tests for the HostInfo class."""

  def _ReadDMISerial(self, name):
    fake_dmi_values = {
        'chassis_serial': 'test_serial',
        'product_uuid': 'test_uuid',
    }
    return fake_dmi_values.get(name, None)

  def _ReadDMIMachineUUID(self, name):
    fake_dmi_values = {
        'chassis_serial': None,
        'product_uuid': 'test_uuid',
    }
    return fake_dmi_values.get(name, None)

  def _ReadDMIRandom(self, name):
    fake_dmi_values = {
        'chassis_serial': None,
        'product_uuid': None,
    }
    return fake_dmi_values.get(name, None)

  def _FakeTime(self):
    return '20171012-135619'

  def _FakeAskText(self, _, mandatory=False):
    if mandatory:
      return 'fake mandatory value'
    return 'fake value'

  def testGetIdendifierWithSerial(self):
    hostinfo.ReadDMI = self._ReadDMISerial
    self.assertEqual(hostinfo.GetIdentifier(), 'test_serial')

  def testGetIdendifierWithUUID(self):
    hostinfo.ReadDMI = self._ReadDMIMachineUUID
    self.assertEqual(hostinfo.GetIdentifier(), 'test_uuid')

  def testGetIdendifierWithRandomUUID(self):
    hostinfo.ReadDMI = self._ReadDMIRandom
    uuid_ = uuid.uuid4()
    with mock.patch('uuid.uuid4', lambda: uuid_):
      self.assertEqual(hostinfo.GetIdentifier(), str(uuid_))
