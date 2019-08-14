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
"""Tests for the auto_forensicate script."""

from __future__ import unicode_literals

import argparse
import logging
import os
import sys
import tempfile
import unittest
from six import StringIO
import mock

from auto_forensicate import auto_acquire
from auto_forensicate import errors
from auto_forensicate import uploader
from auto_forensicate.recipes import base

DEFAULT_ARTIFACT_CONTENT = os.urandom(1000)


# pylint: disable=missing-docstring
# pylint: disable=protected-access

class BytesIORecipe(base.BaseRecipe):
  """A Recipe returning 1 artifact with a BytesIO."""

  def __init__(self, name, options=None):
    super(BytesIORecipe, self).__init__(name, options=options)
    self.ran_collection = False

  def GetArtifacts(self):
    return [base.StringArtifact('fake/path', DEFAULT_ARTIFACT_CONTENT)]


class FailingRecipe(base.BaseRecipe):
  """A Recipe raising an IOError when running GetArtifact."""

  def GetArtifacts(self):
    raise errors.RecipeException('Everything is terrible.')


class FileCopyUploader(object):
  """Test implementation of an Uploader object that copies content to a file."""

  def __init__(self, destination_file):
    self._origin_dir = os.getcwd()
    self.destination_file = destination_file

  def UploadArtifact(self, artifact, update_callback=None):
    data = artifact._GetStream().read()
    self.destination_file.write(data)
    if update_callback:
      update_callback(len(data), len(data))


class BarTest(unittest.TestCase):
  """Tests for the progress bar classes."""

  def testHumanReadableSpeed(self):
    """Tests _HumanReadableSpeed."""
    progressbar = auto_acquire.BaBar()

    self.assertEqual(progressbar._HumanReadableSpeed(0.0), '0.0 B/s')
    expected = [
        '1.2 B/s', '12.3 B/s', '123.0 B/s',
        '1.2 KB/s', '12.3 KB/s', '123.0 KB/s',
        '1.2 MB/s', '12.3 MB/s', '123.0 MB/s',
        '1.2 GB/s', '12.3 GB/s', '123.0 GB/s',
        '1.2 TB/s', '12.3 TB/s', '123.0 TB/s',
        '1.2 PB/s', '12.3 PB/s', '123.0 PB/s',
        '1230.0 PB/s', '12300.0 PB/s', '123000.0 PB/s',
    ]
    for index, value in enumerate(expected):
      self.assertEqual(
          progressbar._HumanReadableSpeed(1.23 * (10 ** index)), value)


class AutoForensicateTest(unittest.TestCase):
  """Tests for the AutoForensicate class.

  TODO(romaing): Add tests for Main(), by setting sys.argv and testing
    the proper recipes ran.
  """

  def FakeBadParseGCSJSON(self, _):
    return None

  def FakeParseGCSJSON(self, _):
    return {'client_id': 'fake_client_id'}

  def FakeMakeProgressBar(self, max_size, name, message=None):  # pylint: disable=unused-argument
    return mock.create_autospec(auto_acquire.BaBar, spec_set=True)

  def testParseDestination(self):
    recipes = {
        'test1': None,
        'test2': None
    }
    af = auto_acquire.AutoForensicate(recipes=recipes)
    test_args = ['--acquire', 'all', 'destination_url']
    options = af.ParseArguments(test_args)
    self.assertEqual(options.destination, 'destination_url')

  def testParseArgsRequiredJson(self):
    recipes = {
        'test1': None,
        'test2': None
    }
    af = auto_acquire.AutoForensicate(recipes=recipes)
    test_args = ['--acquire', 'test1', '--logging', 'stackdriver']
    with self.assertRaises(SystemExit):
      prev_stderr = sys.stderr
      sys.stderr = StringIO()
      af.ParseArguments(test_args)
    sys.stderr = prev_stderr

  def testParseArgsRequiredURL(self):
    recipes = {
        'test1': None,
        'test2': None
    }
    af = auto_acquire.AutoForensicate(recipes=recipes)
    test_args = ['--acquire', 'test1', '--gs_keyfile=null']
    prev_stderr = sys.stderr
    sys.stderr = StringIO()
    with self.assertRaises(SystemExit):
      af.ParseArguments(test_args)
    sys.stderr = prev_stderr

  def testParseAcquireOneRecipe(self):
    recipes = {
        'test1': None,
        'test2': None
    }
    test_args = ['--acquire', 'test1', 'nfs://destination']
    af = auto_acquire.AutoForensicate(recipes=recipes)
    parser = af._CreateParser()
    options = parser.parse_args(test_args)
    expected_recipes = ['test1']
    self.assertEqual(options.acquire, expected_recipes)

  def testParseAcquireBad(self):
    recipes = {
        'test1': None,
        'test2': None
    }
    af = auto_acquire.AutoForensicate(recipes=recipes)
    test_args = [
        '--acquire', 'test4', '--acquire', 'all',
        '--gs_keyfile=file', 'gs://bucket']
    prev_stderr = sys.stderr
    sys.stderr = StringIO()
    with self.assertRaises(SystemExit):
      af.ParseArguments(test_args)
    sys.stderr = prev_stderr

  def testParseAcquireAll(self):
    recipes = {
        'test1': None,
        'test2': None
    }
    af = auto_acquire.AutoForensicate(recipes=recipes)
    test_args = ['--acquire', 'test1', '--acquire', 'all', 'gs://bucket']
    options = af.ParseArguments(test_args)
    expected_recipes = ['test1', 'test2']
    self.assertEqual(options.acquire, expected_recipes)

  def testMakeUploader(self):
    af = auto_acquire.AutoForensicate(recipes={'test': None})

    options = af.ParseArguments(['--acquire', 'all', 'destination'])
    uploader_object = af._MakeUploader(options)
    self.assertEqual(uploader_object, None)

    options = af.ParseArguments(['--acquire', 'all', 'gs://destination'])
    with self.assertRaises(errors.BadConfigOption):
      # We need a --gs_keyfile option for gs:// URLs
      uploader_object = af._MakeUploader(options)

    af._ParseGCSJSON = self.FakeBadParseGCSJSON
    options = af.ParseArguments(
        ['--acquire', 'all', '--gs_keyfile', 'keyfile', 'gs://destination'])
    with self.assertRaises(errors.BadConfigOption):
      # Invalid gs_keyfile
      uploader_object = af._MakeUploader(options)

    af._ParseGCSJSON = self.FakeParseGCSJSON
    options = af.ParseArguments(
        ['--acquire', 'all', '--gs_keyfile', 'keyfile', 'gs://destination'])
    uploader_object = af._MakeUploader(options)
    self.assertIsInstance(uploader_object, uploader.GCSUploader)

  def testFailDo(self):
    af = auto_acquire.AutoForensicate(recipes={})
    recipe = FailingRecipe('fail')
    with tempfile.TemporaryFile() as destination:
      uploader_object = FileCopyUploader(destination)
      af._uploader = uploader_object
      with self.assertRaises(errors.RecipeException):
        af.Do(recipe)

  def testDo(self):
    af = auto_acquire.AutoForensicate(recipes={})
    parser = argparse.ArgumentParser()
    parser.add_argument('--fake', action='store_true')
    options = parser.parse_args(['--fake'])
    af._logger = logging.getLogger(self.__class__.__name__)
    af._MakeProgressBar = self.FakeMakeProgressBar

    recipe = BytesIORecipe('stringio', options=options)
    self.assertTrue(recipe._options.fake)

    with tempfile.TemporaryFile() as destination:
      uploader_object = FileCopyUploader(destination)
      af._uploader = uploader_object
      af.Do(recipe)
      destination.seek(0)
      copied_data = destination.read()
      self.assertEqual(copied_data, DEFAULT_ARTIFACT_CONTENT)


if __name__ == '__main__':
  unittest.main()
