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
"""Tests for the uploader module."""

from __future__ import unicode_literals

import argparse
from collections import namedtuple
import json
try:
  from BytesIO import BytesIO
except ImportError:
  from io import BytesIO
import tempfile
import unittest

import boto
import mock
import shutil

from auto_forensicate import errors
from auto_forensicate import uploader
from auto_forensicate.recipes import base
from auto_forensicate.stamp import manager


# pylint: disable=missing-docstring
# pylint: disable=protected-access

class FakeStamp(
    namedtuple('Stamp', [
        'asset_tag',
        'identifier',
        'start_time'
    ])):
  pass

FAKE_STAMP = FakeStamp(
    asset_tag='fake_asset_tag',
    identifier='fake_uuid',
    start_time='20171012-135619'
)

FAKE_STAMP_NO_ASSET = FakeStamp(
    asset_tag=None,
    identifier='fake_uuid',
    start_time='20171012-135619'
)

class FakeGCSUploader(uploader.GCSUploader):
  """Fake class for the GCSUploader."""


  def __init__(self, gcs_url):
    """Initializes the GCSUploader class.

    Args:
      gcs_url (str): the GCS url to the bucket and remote path.
    """
    super(FakeGCSUploader, self).__init__(
        gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager(),
        stamp=FAKE_STAMP)
    self._uploaded_streams = {}

  def _UploadStream(self, stream, remote_path, update_callback=None):
    """Fakes the uploading of a file object.

    This stores the content of the stream and remote_path in _uploaded_streams
    as a dict of {remote_path: stream_content}

    Args:
      stream (file): the file-like object pointing to data to upload.
      remote_path (str): the remote path to store the data to.
      update_callback (func): an optional function called as upload progresses.
    """
    self._uploaded_streams[remote_path] = stream.read().decode('utf-8')


class FakeStampManager(manager.BaseStampManager):

  def GetStamp(self):
    return FakeStamp(
        asset_tag='fake_asset_tag',
        identifier='fake_uuid',
        start_time='20171012-135619')


class LocalCopierTests(unittest.TestCase):
  """Tests for the LocalCopier class."""

  def setUp(self):
    self.temp_dir = tempfile.mkdtemp()

  def tearDown(self):
    pass
    #shutil.rmtree(self.temp_dir)

  @mock.patch.object(base.BaseArtifact, '_GetStream')
  def testUploadArtifact(self, patched_getstream):
    test_artifact = base.BaseArtifact('test_artifact')
    patched_getstream.return_value = BytesIO(b'fake_content')

    uploader_object = uploader.LocalCopier(
        self.temp_dir, FakeStampManager(), stamp=FAKE_STAMP)

    expected_artifact_path = (
        self.temp_dir+'/20171012-135619/fake_uuid/Base/test_artifact')
    expected_artifact_content = 'fake_content'

    expected_stamp_path = (
        self.temp_dir+'/20171012-135619/fake_uuid/stamp.json')
    expected_stamp_content = json.dumps(FAKE_STAMP._asdict())

    result_path = uploader_object.UploadArtifact(test_artifact)

    self.assertEqual(expected_artifact_path, result_path)
    with open(result_path, 'r') as artifact_file:
      self.assertEqual(expected_artifact_content, artifact_file.read())

    with open(expected_stamp_path, 'r') as stamp_file:
      self.assertEqual(expected_stamp_content, stamp_file.read())


class GCSUploaderTests(unittest.TestCase):
  """Tests for the GCSUploader class."""

  def setUp(self):
    self.gcs_bucket = 'bucket_name'
    self.gcs_path = 'some/where'
    self.gcs_url = 'gs://{0:s}/{1:s}'.format(self.gcs_bucket, self.gcs_path)

  def testMakeRemotePathNoAsset(self):
    uploader_object = uploader.GCSUploader(
        self.gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager(),
        stamp=FAKE_STAMP_NO_ASSET)
    remote_name = 'remote_file'

    expected_remote_path = (
        'bucket_name/some/where/20171012-135619/fake_uuid/remote_file')
    remote_path = uploader_object._MakeRemotePath(remote_name)
    self.assertEqual(remote_path, expected_remote_path)

  def testMakeRemotePath(self):
    uploader_object = uploader.GCSUploader(
        self.gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager(),
        stamp=FAKE_STAMP)
    remote_name = 'remote_file'

    expected_remote_path = (
        'bucket_name/some/where/20171012-135619/fake_uuid/'
        'remote_file')
    remote_path = uploader_object._MakeRemotePath(remote_name)
    self.assertEqual(remote_path, expected_remote_path)

  def testSplitGCSUrl(self):
    self.gcs_url = 'gs://bucket_name/some/where'
    uploader_object = uploader.GCSUploader(
        self.gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager())
    expected_tuple = ('bucket_name', 'some/where')
    self.assertEqual(uploader_object._SplitGCSUrl(), expected_tuple)

    self.gcs_url = 'gs://bucket_name'
    uploader_object = uploader.GCSUploader(
        self.gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager())
    expected_tuple = ('bucket_name', '')
    self.assertEqual(uploader_object._SplitGCSUrl(), expected_tuple)

    self.gcs_url = 'gs://bucket_name/'
    uploader_object = uploader.GCSUploader(
        self.gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager())
    expected_tuple = ('bucket_name', '')
    self.assertEqual(uploader_object._SplitGCSUrl(), expected_tuple)

    self.gcs_url = 'invalid'
    uploader_object = uploader.GCSUploader(
        self.gcs_url, 'fake_key.json', 'fake_clientid', FakeStampManager())
    with self.assertRaisesRegexp(
        argparse.ArgumentError, 'Invalid GCS URL \'{0:s}\''.format('invalid')):
      uploader_object._SplitGCSUrl()

  @mock.patch.object(base.BaseArtifact, '_GetStream')
  def testUploadArtifact(self, patched_getstream):
    test_artifact = base.BaseArtifact('test_artifact')
    patched_getstream.return_value = BytesIO(b'fake_content')

    uploader_object = FakeGCSUploader(self.gcs_url)

    expected_resultpath = (
        'bucket_name/some/where/20171012-135619/fake_uuid/Base/'
        'test_artifact')
    expected_uploaded_streams = {
        ('bucket_name/some/where/20171012-135619/fake_uuid/'
         'Base/test_artifact'): 'fake_content',
        ('bucket_name/some/where/20171012-135619/fake_uuid/'
         'stamp.json'): json.dumps(FAKE_STAMP._asdict())
    }

    result_path = uploader_object.UploadArtifact(test_artifact)
    self.assertEqual(result_path, expected_resultpath)
    self.assertEqual(
        uploader_object._uploaded_streams, expected_uploaded_streams)

  @mock.patch.object(base.BaseArtifact, '_GetStream')
  @mock.patch.object(boto, 'storage_uri')
  def testFailUploadRetryWorthy(self, patched_storage, patched_getstream):
    patched_getstream.return_value = BytesIO(b'fake_content')
    patched_storage.side_effect = boto.exception.GSDataError('boom')

    test_artifact = base.BaseArtifact('test_artifact')

    uploader_object = uploader.GCSUploader(
        'gs://fake_bucket/', 'no_keyfile', 'client_id', FakeStampManager())
    uploader_object._boto_configured = True

    with self.assertRaises(errors.RetryableError):
      uploader_object._UploadStream(
          test_artifact.OpenStream(), 'gs://fake_bucket/remote/path')

  @mock.patch.object(base.BaseArtifact, '_GetStream')
  @mock.patch.object(boto, 'storage_uri')
  def testFailUploadNoRetry(self, patched_storage, patched_getstream):
    patched_getstream.return_value = BytesIO(b'fake_content')
    patched_storage.side_effect = errors.ForensicateError('random_error')

    test_artifact = base.BaseArtifact('test_artifact')

    uploader_object = uploader.GCSUploader(
        'gs://fake_bucket/', 'no_keyfile', 'client_id', FakeStampManager())
    uploader_object._boto_configured = True

    with self.assertRaises(errors.ForensicateError):
      uploader_object._UploadStream(
          test_artifact.OpenStream(), 'gs://fake_bucket/remote/path')
