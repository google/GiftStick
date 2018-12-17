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
"""Set of helper functions for the end to end tests."""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import re

try:
  from urlparse import urlparse
except ImportError:
  from urllib.parse import urlparse


def NormalizeGCSURL(url):
  """Normalize a GCS URL.

  Args:
    url(str): the gs URL to normalize (ie: 'gs://bucket/path/')

  Returns:
    str: the normalized URL
  """
  parsed_url = urlparse(url)
  path_with_no_double_slash = parsed_url.path.replace('//', '/')
  parsed_url = parsed_url._replace(path=path_with_no_double_slash)
  return parsed_url.geturl()

def CheckStamp(stamp_path):
  """Checks the content of a GiftStick stamp.json file.

  Args:
    stamp_path(str): path to the stamp file.

  Raises:
    Exception: if the stamp's content aren't correct.
  """
  stamp_dict = {}
  with open(stamp_path) as stamp_file:
    stamp_dict = json.load(stamp_file)

  identifier_regex = re.compile(
      '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
  assert identifier_regex.match(stamp_dict.get('identifier'))

  start_time_regex = re.compile('^[0-9]{8}-[0-9]{6}$')
  assert start_time_regex.match(stamp_dict.get('start_time'))

def CheckSystemInfo(system_info_path):
  """Checks the content of a GiftStick stamp.json file.

  Args:
    system_info_path(str): path to the system_info.txt file.

  Raises:
    Exception: if the input file's content aren't correct.
  """

  system_info = ''
  with open(system_info_path, 'r') as system_info_file:
    system_info = system_info_file.read()

  sysinfo_regex = re.compile(
      'System Information\n\W+Manufacturer: QEMU', re.MULTILINE)
  assert sysinfo_regex.search(system_info)


def ParseArguments():
  """Parse arguments

  Returns:
    argparse.Namespace: the parsed command-line arguments.
  """
  parser = argparse.ArgumentParser(
      description='Helper functions for end to end tests.')
  subparsers = parser.add_subparsers(
      title='commands', description='valid sub-commands', dest='command')

  normalize = subparsers.add_parser(
      'normalize', help='Helps normalize a GCS URL')
  normalize.add_argument('url', type=str, help='the GCS URL to normalize')

  check_stamp = subparsers.add_parser(
      'check_stamp', help='Checks the content of a GiftStick Stamp file')
  check_stamp.add_argument(
      'stamp', type=str, help='the stamp.json file to check')

  check_system_info = subparsers.add_parser(
      'check_system_info',
      help='Checks the content of the system_info.txt file')
  check_system_info.add_argument(
      'system_info', type=str, help='the system_info.txt file to check')

  return parser.parse_args()

if __name__ == '__main__':
  options = ParseArguments()

  if options.command == 'normalize':
    print(NormalizeGCSURL(options.url))
  elif options.command == 'check_stamp':
    CheckStamp(options.stamp)
  elif options.command == 'check_system_info':
    CheckSystemInfo(options.system_info)
