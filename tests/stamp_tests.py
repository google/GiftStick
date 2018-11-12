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
"""Tests for the stamp module."""

from __future__ import unicode_literals

import unittest
import mock
from auto_forensicate.stamp.manager import BaseStamp
from auto_forensicate.stamp.manager import StampManager


class StampManagerTests(unittest.TestCase):
  """Tests for the StampManager class."""

  def setUp(self):
    self.test_stamp = BaseStamp(
        identifier='test_uuid',
        start_time='20171012-135619')

  def testBaseElements(self):
    path_elements = ['20171012-135619', 'test_uuid']
    stamp_manager = StampManager()
    self.assertEqual(
        stamp_manager.BasePathElements(self.test_stamp), path_elements)

  def testGetStamp(self):
    test_stamp = BaseStamp(
        identifier='test_uuid',
        start_time='20171012-135619')
    with mock.patch('auto_forensicate.hostinfo.GetTime') as faked_time:
      faked_time.return_value = '20171012-135619'
      with mock.patch('auto_forensicate.hostinfo.GetIdentifier') as faked_id:
        faked_id.return_value = 'test_uuid'
        stamp_manager = StampManager()
        self.assertEqual(stamp_manager.GetStamp(), test_stamp)
