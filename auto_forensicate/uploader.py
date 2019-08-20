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
"""Implements various cloud upload helpers."""

from __future__ import unicode_literals

import argparse
import json
import logging
import os
try:
  from BytesIO import BytesIO
except ImportError:
  from io import BytesIO
from six.moves.urllib.parse import urlparse
import boto
from auto_forensicate import errors

class BaseUploader(object):
  """Base class for an Uploader object."""

  def __init__(self, stamp_manager, stamp=None):
    """Initializes the BaseUploader class.

    Args:
      stamp_manager (StampManager): the StampManager object for this
        context.
      stamp (namedtuple): an optional ForensicsStamp containing
        the upload metadata.
    """
    self._stamp_manager = stamp_manager
    self._logger = logging.getLogger(self.__class__.__name__)

    self._stamp = stamp or self._stamp_manager.GetStamp()
    self._stamp_uploaded = False

  def _UploadStamp(self):
    """Upload the 'stamp' (a json file containing metadata)."""

    # TODO: if this fails, raise an Exception that will stop execution
    stream = BytesIO(json.dumps(self._stamp._asdict()).encode('utf-8'))
    remote_path = self._MakeRemotePath('stamp.json')
    self._UploadStream(stream, remote_path)
    self._stamp_uploaded = True
    self._logger.info('Uploaded %s', remote_path)

  def _MakeRemotePath(self, destination):
    """Builds the remote path for an object.

    Args:
      destination (str): the destination path for the artifact.
    Returns:
      str: the sanitized remote path.
    """

    remote_path_elems = self._stamp_manager.BasePathElements(self._stamp)
    remote_path = '/'.join(remote_path_elems + [destination])

    return remote_path

  def _UploadStream(self, stream, remote_path, update_callback=None):
    """Uploads a file object to Google Cloud Storage.

    Args:
      stream (file): the file-like object pointing to data to upload.
      remote_path (str): the remote path to store the data to.
      update_callback (func): an optional function called as upload progresses.

    Raises:
      NotImplementedError: if the method is not implemented.
    """
    raise NotImplementedError('Please implement _UploadStream')

  def UploadArtifact(self, artifact, update_callback=None):
    """Uploads a file object to Google Cloud Storage.

    Args:
      artifact (BaseArtifact): the Artifact object pointing to data to upload.
      update_callback (func): an optional function called as upload progresses.

    Returns:
      str: the remote destination where the file was uploaded.
    """

    # Upload the 'stamp' file. This allows us to make sure we have write
    # permission on the bucket, and fail early if we don't.
    if not self._stamp_uploaded:
      self._UploadStamp()

    remote_path = self._MakeRemotePath(artifact.remote_path)
    self._UploadStream(
        artifact.OpenStream(), remote_path, update_callback=update_callback)

    artifact.CloseStream()
    return remote_path


class LocalCopier(BaseUploader):
  """Handles uploads of data to a local directory."""

  def __init__(self, destination_dir, stamp_manager, stamp=None):
    """Initializes the LocalCopier class.

    Args:
      destination_dir (str): the path to the destination directory.
      stamp_manager (StampManager): the StampManager object for this
        context.
      stamp (namedtuple): an optional ForensicsStamp containing
        the upload metadata.
    """
    super(LocalCopier, self).__init__(stamp_manager=stamp_manager, stamp=stamp)
    self.destination_dir = destination_dir

  def _UploadStream(self, stream, remote_path, update_callback=None):
    """Copies a file object to a remote directory.

    Args:
      stream (file): the file-like object pointing to data to upload.
      remote_path (str): the remote path to store the data to.
      update_callback (func): an optional function called as upload progresses.
    """

    destination_file = open(remote_path, 'wb')
    copied = 0
    buffer_length = 16*1024 # This is the defaults for shutil.copyfileobj()
    while True:
      buf = stream.read(buffer_length)
      if not buf:
        break
      destination_file.write(buf)
      copied += len(buf)
      if update_callback:
        update_callback(len(buf), copied)

  def _MakeRemotePath(self, destination):
    """Builds the remote path for an object.

    Args:
      destination (str): the destination path for the artifact.
    Returns:
      str: the sanitized remote path.
    """

    remote_path_elems = (
        [self.destination_dir] +
        self._stamp_manager.BasePathElements(self._stamp) + [destination])
    remote_path = '/'.join(remote_path_elems)

    base_dir = os.path.dirname(remote_path)
    if not os.path.exists(base_dir):
      os.makedirs(base_dir)

    return remote_path


class GCSUploader(BaseUploader):
  """Handles resumable uploads of data to Google Cloud Storage."""

  def __init__(self, gs_url, gs_keyfile, client_id, stamp_manager, stamp=None):
    """Initializes the GCSUploader class.

    Args:
      gs_url (str): the GCS url to the bucket and remote path.
      gs_keyfile (str): path of the private key for the Service Account.
      client_id (str): the client ID set in the credentials file.
      stamp_manager (StampManager): the StampManager object for this
        context.
      stamp (namedtuple): an optional ForensicsStamp containing
        the upload metadata.
    """
    super(GCSUploader, self).__init__(stamp_manager=stamp_manager, stamp=stamp)
    self._boto_configured = False
    self._bucket_name = None
    self._client_id = client_id
    self._gs_keyfile = os.path.abspath(gs_keyfile)
    self._gs_url = gs_url

  def _InitBoto(self):
    """Initializes the boto library with credentials from self._gs_keyfile."""

    if not boto.config.has_section('Credentials'):
      boto.config.add_section('Credentials')

    boto.config.set(
        'Credentials', 'gs_service_key_file', self._gs_keyfile)
    boto.config.set(
        'Credentials', 'gs_service_client_id', self._client_id)

    self._boto_configured = True

  def _SplitGCSUrl(self):
    """Extracts the bucket name and remote base path from the gs_url argument.

    Returns:
      (str, str): a tuple containing GCS bucket name, and the remote base path.

    Raises:
      argparse.ArgumentError: if gs_url is invalid
    """
    parsed_url = urlparse(self._gs_url)
    if parsed_url.scheme != 'gs':
      raise argparse.ArgumentError(
          None, 'Invalid GCS URL \'{0:s}\''.format(self._gs_url))

    bucket_name = parsed_url.netloc
    gs_base_path = parsed_url.path

    # This takes care of "//" in a url
    remote_base_path = '/'.join(filter(None, gs_base_path.split('/')))

    return (bucket_name, remote_base_path)

  def _MakeRemotePath(self, destination):
    """Builds the remote path for an object.

    Args:
      destination (str): the destination path for the artifact.
    Returns:
      str: the sanitized remote path.
    """

    remote_path_elems = self._stamp_manager.BasePathElements(self._stamp)
    remote_path = '/'.join(remote_path_elems)
    base_path = None

    self._bucket_name, base_path = self._SplitGCSUrl()

    if base_path:
      remote_path = '/'.join([base_path, remote_path])

    if destination:
      remote_path = '/'.join([remote_path, destination])

    remote_path = '/'.join([self._bucket_name, remote_path])

    return remote_path

  def _UploadStream(self, stream, remote_path, update_callback=None):
    """Uploads a file object to Google Cloud Storage.

    Args:
      stream (file): the file-like object pointing to data to upload.
      remote_path (str): the remote path to store the data to.
      update_callback (func): an optional function called as upload progresses.
    Raises:
      errors.RetryableError: when the upload encounters an error that's worth
        retrying.
    """
    if not self._boto_configured:
      self._InitBoto()

    try:
      dst_uri = boto.storage_uri(remote_path, u'gs')
      dst_uri.new_key().set_contents_from_stream(stream, cb=update_callback)
    except boto.exception.GSDataError as e:
      # This is usually raised when the connection is broken, and deserves to
      # be retried.
      raise errors.RetryableError(str(e))
