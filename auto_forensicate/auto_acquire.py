#!/usr/bin/env python
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
"""Automated forensics acquisition script."""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import logging
import sys
import time

import gcs_oauth2_boto_plugin  # pylint: disable=unused-import
from google.cloud import logging as cloud_logging
from google.cloud.logging_v2 import logger as cloud_logger
from google.cloud.logging_v2 import handlers as cloud_handlers
from google.oauth2 import service_account
from progress.bar import IncrementalBar
from progress.spinner import Spinner

from auto_forensicate import errors
from auto_forensicate import hostinfo
from auto_forensicate import uploader
from auto_forensicate.recipes import directory
from auto_forensicate.recipes import disk
from auto_forensicate.recipes import firmware
from auto_forensicate.recipes import sysinfo
from auto_forensicate.stamp import manager

VALID_RECIPES = {
    'directory': directory.DirectoryRecipe,
    'disk': disk.DiskRecipe,
    'firmware': firmware.ChipsecRecipe,
    'sysinfo': sysinfo.SysinfoRecipe
}

# These recipes will all be executed when 'all' recipes are specified
DEFAULT_RECIPES = frozenset({'disk', 'firmware', 'sysinfo'})
ARTIFACT_MIN_REPORTING_SIZE = 1024**3

def HumanReadableBytes(byte_val, prefix='dec'):
  """Converts a byte count into a human readable form in MB/MiB etc

  Args:
    byte_val (int): a byte count.
    prefix (str): what prefix system to use, bin (KiB) or dec (KB)
  Returns:
    str: A human-readable byte count.
  """

  if prefix == 'bin':
    kilo = 1024
    suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  elif prefix == 'dec':
    kilo = 1000
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

  for i in range(0, 6):
    if byte_val < kilo ** (i+1):
      return '{:.1f} {:s}'.format(byte_val / kilo**i, suffixes[i])
  return '{:.1f} {:s}'.format(byte_val / kilo**5, suffixes[5])


class SpinnerBar(Spinner):
  """A Spinner object with an extra update method."""

  #pylint: disable=invalid-name
  def update_with_total(self, _unused_current_bytes, _unused_total_bytes):
    """Called by boto library to update the ProgressBar.

    Args:
      _unused_current_bytes(int): the number of bytes uploaded.
      _unused_total_bytes(int): the total number of bytes to upload.
    """
    self.next()


class BaBar(IncrementalBar):
  """An IncrementalBar object with an extra update method.

    This is required because the boto library's callback expects a function that
    takes two arguments (with the cumulated value), while progress.Bar
    expects an increment.
  """

  def _Update(self, current_bytes):
    """Updates the current state of the progress Bar.

    Args:
      current_bytes(int): the number of bytes uploaded.
    """
    # pylint: disable=access-member-before-definition
    # pylint: disable=attribute-defined-outside-init
    now = time.time()
    dt = now - self._ts
    self.update_avg((current_bytes - self.index), dt)
    self._ts = now
    self.index = current_bytes

    try:
      self.update()
    except OverflowError:
      # When calculating a sliding ETA, the progress module will cast int()
      # on values that can be very large (ie: 'lots of bytes, only sent a few
      # of them just now)
      # Passing here just might mess up the "ETA" part of the progress bar
      # message, but prevents us from crashing. See:
      # https://github.com/google/GiftStick/issues/92
      pass

  @property
  def speed(self):
    """Returns a human readable version of the current upload speed."""
    if self.avg == 0:
      return 'NaN'
    return HumanReadableBytes(1 / self.avg) + '/s'

  #pylint: disable=invalid-name
  def update_with_total(self, current_bytes, _unused_total_bytes):
    """Called by boto library to update the ProgressBar.

    Args:
      current_bytes(int): the number of bytes uploaded.
      _unused_total_bytes(int): the total number of bytes to upload.
    """
    self._Update(current_bytes)


class GCPProgressReporter:
  """Class implementing Stackdriver progress reporting.

    Attributes:
      _artifact (BaseArtifact): the artifact being uploaded.
      _progress_logger (google.cloud.logging.logger.Logger):
        the Stackdriver logger for progress reporting.
  """

  def __init__(self, artifact, progress_logger, reporting_frequency=5):
    """Instantiates the GCPProgressReporter object.

    Args:
      artifact (BaseArtifact): the artifact to be uploaded.
      progress_logger (google.cloud.logging.logger.Logger): the Stackdriver
        logger.
      reporting_frequency (int): what percentage change in progress to report
        defaults to 5%.
    """
    self._artifact = artifact
    self._progress_logger = progress_logger
    self._reporting_frequency = reporting_frequency
    self._reported_percentage = 0

  def _CheckReportable(self, percentage):
    """Returns a bool indicating if the current percentage shoud be reported.

    Args:
      percentage (int): the current percentage uploaded.
    Returns:
      bool: whether to report this percentage.
    """
    if percentage % self._reporting_frequency == 0:
      if percentage != self._reported_percentage:
        return True
    return False

  #pylint: disable=invalid-name
  def update_with_total(self, current_bytes, _unused_total_bytes):
    """Called by boto callback handling logic to report progress.

    Args:
      current_bytes(int): the number of bytes uploaded.
      _unused_total_bytes(int): the total number of bytes to upload.
    """
    percentage = int(current_bytes / self._artifact.size * 100)
    bytes_remaining = self._artifact.size - current_bytes

    if self._CheckReportable(percentage):
      self._progress_logger.log_text(
          'Uploading \'{:s}\' ({:d}% - {:s} remaining)'.format(
              self._artifact.name, percentage,
              HumanReadableBytes(bytes_remaining, 'bin')),
          severity='INFO')
      self._reported_percentage = percentage


class BotoCallbackHandler:
  """Class implementing boto update_callback handling logic.

    Attributes:
      _callbacks ([function]): a list of callback functions.
  """

  def __init__(self):
    """Instantiates the BotoCallbackHandler object."""
    self._callbacks = []

  def RegisterCallback(self, callback):
    """Register a callback to be called on boto callbacks.

    Args:
      callback (function): the callback function to be registered.
    """
    self._callbacks.append(callback)

  #pylint: disable=invalid-name
  def update_with_total(self, current_bytes, total_bytes):
    """Called by boto library during uploads.

    Args:
      current_bytes(int): the number of bytes uploaded.
      total_bytes(int): the total number of bytes to upload.
    """
    for callback in self._callbacks:
      callback(current_bytes, total_bytes)


class AutoForensicate(object):
  """Class implementing forensics acquisition logic.

    Attributes:
      _recipes (dict[str, BaseRecipe]): the list of valid recipes.
  """

  def __init__(self, recipes=None):
    """Instantiates the AutoForensicate object.

    Args:
      recipes (dict[str, BaseRecipe]): the dict listing available recipes.
    Raises:
      errors.BadConfigOption: if no available recipes dict is passed.
    """
    if recipes is None:
      raise errors.BadConfigOption('The recipes argument must not be None')

    self._errors = []
    self._gcs_settings = None
    self._logger = None
    self._progress_logger = None
    self._recipes = recipes
    self._uploader = None
    self._should_retry = False  # True when a recoverable error occurred.
    self._stackdriver_handler = None  # Stackdriver backed logging handler.

  def _CreateParser(self):
    """Returns an instance of argparse.ArgumentParser."""
    parser = argparse.ArgumentParser(
        description='Autopush forensics evidence to Cloud Storage')
    parser.add_argument(
        '--no-zenity', action='store_true', default=False,
        help='Disable Zenity for user interactions')

    parser.add_argument(
        '--acquire', action='append', help='Evidence to acquire',
        choices=['all']+sorted(list(self._recipes.keys())), required=True
    )
    parser.add_argument(
        'destination', action='store',
        help=(
            'Sets the destination for uploads. '
            'For example gs://bucket_name/path will upload to GCS in bucket '
            '<bucket_name> in the folder </path/>')
    )
    parser.add_argument(
        '--gs_keyfile', action='store', required=False,
        help=(
            'Path to the service account private key JSON file for Google '
            'Cloud')
    )
    parser.add_argument(
        '--logging', action='append', required=False,
        choices=['stackdriver', 'stdout'], default=['stdout'],
        help='Selects logging methods.'
    )
    parser.add_argument(
        '--log_progress', action='store_true', default=False,
        help=(
            'Enable logging of acquisition progress to stackdriver, requires '
            'stackdriver to be selected with --logging')
    )
    parser.add_argument(
        '--select_disks', action='store_true', required=False, default=False,
        help='Asks the user to select which disk to acquire'
    )
    parser.add_argument(
        '--disk', action='append', required=False,
        help='Specify a disk to acquire (eg: sda)'
    )
    parser.add_argument(
        '--disable_dcfldd', action='store_true', required=False,
        help=(
            'Do not use dcfldd to acquire a disk, just read blocks '
            '(this disable creation of hashlog files)')
    )
    parser.add_argument(
        '--method', action='store', required=False, choices=['tar'],
        default='tar',
        help='Specify which method to use when acquiring a directory'
    )
    parser.add_argument(
        '--compress', action='store_true', required=False, default=False,
        help='Specify which method to use when acquiring a directory'
    )
    return parser

  def _ParseLoggingArguments(self, options):
    """Parses the --logging flag.

    Args:
      options (argparse.Namespace): the parsed command-line arguments.
    Raises:
      errors.BadConfigOption: if the options are invalid.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    self._logger = logging.getLogger(self.__class__.__name__)

    if 'stackdriver' in options.logging:
      if not self._gcs_settings:
        raise errors.BadConfigOption(
            'Please provide a valid --gs_keyfile to enable StackDriver '
            'logging')
      gcp_credentials = service_account.Credentials.from_service_account_file(
          options.gs_keyfile)
      project_id = self._gcs_settings.get('project_id', None)

      gcp_logging_client = cloud_logging.Client(
          project=project_id, credentials=gcp_credentials)
      self._stackdriver_handler = cloud_handlers.CloudLoggingHandler(
          gcp_logging_client, name='GiftStick')
      self._logger.addHandler(self._stackdriver_handler)

    if options.log_progress:
      if 'stackdriver' not in options.logging:
        raise errors.BadConfigOption(
            'Progress logging requires Stackdriver logging to be enabled')
      self._progress_logger = cloud_logger.Logger(
          'GiftStick', gcp_logging_client)

  def _MakeUploader(self, options):
    """Creates a new Uploader object.

    This instantiates the proper Uploader object to handle the destination URL
    argument.

    Args:
      options (argparse.Namespace): the parsed command-line arguments.
    Returns:
      Uploader: an uploader object.
    Raises:
      errors.BadConfigOption: if the options are invalid.
    """

    stamp_manager = manager.BaseStampManager()

    if options.destination.startswith('gs://'):
      if not self._gcs_settings:
        raise errors.BadConfigOption(
            'Please provide a valid GCS json file. '
            'See --gs_keyfile option'
        )

      client_id = self._gcs_settings.get('client_id', None)

      if not client_id:
        raise errors.BadConfigOption(
            'The provided GCS json file lacks a "client_id" key.'
        )

      return uploader.GCSUploader(
          options.destination, options.gs_keyfile, client_id, stamp_manager)

    if options.destination.startswith('/'):
      return uploader.LocalCopier(options.destination, stamp_manager)

    return None

  def ParseArguments(self, args):
    """Parses the arguments.

    Args:
      args (list): list of arguments.
    Returns:
      argparse.Namespace: parsed command line arguments.
    Raises:
      BadConfigOption: if the arguments are not specified properly.
    """
    parser = self._CreateParser()
    options = parser.parse_args(args)

    self._ParseRecipes(options)
    self._gcs_settings = self._ParseGCSJSON(options)
    self._ParseLoggingArguments(options)

    if options.select_disks and 'disk' not in options.acquire:
      raise errors.BadConfigOption(
          ('--select_disks needs the disk recipe ('
           'current recipes : {0:s})').format(
               ', '.join(options.acquire))
      )

    if not options.no_zenity:
      # force no_zenity to True if zenity is not installed
      zenity_path = hostinfo.Which('zenity')
      if not zenity_path:
        options.no_zenity = True

    return options

  def _ParseRecipes(self, options):
    """Parses the recipes argument flag.

    Args:
      options (argparse.Namespace): the parsed command-line arguments.
    """
    if 'all' in options.acquire:
      options.acquire = sorted(DEFAULT_RECIPES)
    else:
      # Deduplicate recipes
      options.acquire = sorted(list(set(options.acquire)))

  def _ParseGCSJSON(self, options):
    """Parses a GCS json configuration file.

    Args:
      options (argparse.Namespace): the parsed command-line arguments.
    Returns:
      dict: the dict representation of the JSON object in the config file.
    """
    if options.gs_keyfile:
      with open(options.gs_keyfile, 'r') as json_file_descriptor:
        return json.load(json_file_descriptor)
    return None

  def _MakeProgressBar(self, max_size, name, message=None):
    """Returns a ProgressBar object with default widgets.

    Args:
      max_size (int): the size of the source.
      name (str): the name of what is being processed.
      message (str): an extra message to display before the bar.

    Returns:
      ProgressBar: the progress bar object.
    """
    if message:
      self._logger.info(message)
    if max_size > 0:
      pb = BaBar(
          max=max_size,
          # Cf https://github.com/verigak/progress/blob/master/README.rst
          # for the message and suffix templates.
          message=name + ' %(percent).1f%% ',
          suffix=' %(eta_td)s %(speed)s'
      )
    else:
      pb = SpinnerBar(name + ' ')
    return pb

  def _MakeGCPProgressReporter(self, artifact):
    """Returns a GCPProgressReporter object.

    Args:
      artifact (BaseArtifact): the artifact representing the file to upload.

    Returns:
      GCPProgressReporter: the progress reporter object.
    """
    if self._progress_logger:
      if artifact.size > ARTIFACT_MIN_REPORTING_SIZE:
        return GCPProgressReporter(artifact, self._progress_logger)
    return None

  def Do(self, recipe):
    """Runs a recipe.

    Args:
      recipe (BaseRecipe): a recipe object.
    """
    with recipe:
      artifacts = recipe.GetArtifacts()
      self._UploadArtifacts(artifacts)

  def _UploadArtifact(self, artifact, update_callback=None):
    """Uploads one Artifact to a remote storage.

    Args:
      artifact (BaseArtifact): the artifact representing the file to upload.
      update_callback (func): the function called with the arguments:
        number_bytes_uploaded, number_bytes_total
    """
    try:
      remote_path = self._uploader.UploadArtifact(
          artifact, update_callback=update_callback)
      self._logger.info('Uploaded \'%s\'', remote_path)
    except Exception as e:   # pylint: disable=broad-except
      # We need to catch all Exceptions here, as even if one artifact failed to
      # acquire, we want to try uploading others.
      self._logger.exception('Unable to upload artifact %s', artifact.name)
      self._errors.append(e)

  def _UploadArtifacts(self, artifacts):
    """Uploads a list of Artifacts to a remote storage.

    Args:
      artifacts (list[BaseArtifact]): the list of artifacts to upload.
    """
    nb_tasks = len(artifacts)
    current_task = 0
    for artifact in artifacts:
      current_task += 1
      callback_handler = BotoCallbackHandler()
      progress_bar = self._MakeProgressBar(
          artifact.size, artifact.name,
          'Uploading \'{0:s}\' ({1:s}, Task {2:d}/{3:d})'.format(
              artifact.name, artifact.readable_size, current_task, nb_tasks))
      callback_handler.RegisterCallback(progress_bar.update_with_total)
      progress_reporter = self._MakeGCPProgressReporter(artifact)
      if progress_reporter:
        callback_handler.RegisterCallback(progress_reporter.update_with_total)
      self._UploadArtifact(
          artifact, update_callback=callback_handler.update_with_total)
      progress_bar.finish()

  def _Colorize(self, color, msg):
    """Adds a ANSI color to a message.

    Args:
      color(int): The ANSI color escape code.
      msg(str): The message to display.
    Returns:
      str: The colored message.
    """
    reset_color_seq = '\033[0m'
    color_seq = '\033[3{0:d}m'.format(color)

    return color_seq + msg + reset_color_seq

  def Main(self, args=None):
    """Main method for AutoForensicate.

    Args:
      args (list[str]): list of command line arguments.
    Raises:
      Exception: if no Uploader object have been instantiated.
    """
    options = self.ParseArguments(args)

    self._uploader = self._MakeUploader(options)

    if not self._uploader:
      raise Exception('Could not instantiate uploader')

    message = 'Acquisition starting with args \'{0!s}\''.format(sys.argv)
    self._logger.info(message)
    for recipe_name in options.acquire:
      recipe_class = self._recipes.get(recipe_name, None)
      if recipe_class:
        try:
          self.Do(recipe_class(recipe_name, options=options))
        except Exception as e:  # pylint: disable=broad-except
          # We log the error but want to keep acquiring other recipes.
          self._logger.exception('Recipe %s failed to run', recipe_name)
          self._errors.append(e)

    self._logger.info('Acquisition has ended')

    if self._stackdriver_handler:
      # Make sure all logs are sent to StackDriver
      self._stackdriver_handler.transport.worker.stop()
      logging.getLogger().removeHandler(self._stackdriver_handler)

    # The next messages are for the current user only
    red_color_code = 1
    green_color_code = 2

    if self._errors:
      should_retry = False
      # Error management from down here
      for e in self._errors:
        if isinstance(e, errors.RetryableError):
          should_retry = True

      if should_retry:
        print(self._Colorize(
            red_color_code,
            'There was a problem with the upload, please re-run the script.'))
      else:
        print(self._Colorize(
            red_color_code,
            ('There was a problem with the upload, please keep the system '
             'running and contact the security person who told you to do the '
             'GiftStick process')
        ))
    else:
      print(self._Colorize(
          green_color_code,
          ('Everything has completed successfully, feel free to shut the system'
           ' down.')
      ))


if __name__ == '__main__':
  app = AutoForensicate(VALID_RECIPES)
  app.Main(args=sys.argv[1:])
