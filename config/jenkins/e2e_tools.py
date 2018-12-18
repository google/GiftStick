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
    Exception: if the input file content isn't correct.
  """
  stamp_dict = {}
  with open(stamp_path, 'r') as stamp_file:
    stamp_dict = json.load(stamp_file)

  identifier_regex = re.compile(
      r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
  assert identifier_regex.match(stamp_dict.get('identifier'))

  start_time_regex = re.compile(r'^[0-9]{8}-[0-9]{6}$')
  assert start_time_regex.match(stamp_dict.get('start_time'))

def CheckSystemInfo(system_info_path):
  """Checks the content of a GiftStick stamp.json file.

  Args:
    system_info_path(str): path to the system_info.txt file.

  Raises:
    Exception: if the input file content isn't correct.
  """

  system_info = ''
  with open(system_info_path, 'r') as system_info_file:
    system_info = system_info_file.read()

  sysinfo_regex = re.compile(
      r'System Information\n\W+Manufacturer: QEMU', re.MULTILINE)
  assert sysinfo_regex.search(system_info)

def CheckLsblk(lsblk_path):
  """Checks the content of a GiftStick lsblk.txt file.

  Args:
    lsblk_path(str): path to the lsblk.txt file.

  Raises:
    Exception: if the input file content isn't correct.
  """
  lsblk_dict = {}
  with open(lsblk_path) as lsblk_file:
    lsblk_dict = json.load(lsblk_file)

  assert len(lsblk_dict['blockdevices']) == 6
  sdb_disk = [
      dev for dev in lsblk_dict['blockdevices'] if dev['name']=='sdb'][0]

  assert sdb_disk['size'] == '44040192'
  children = sorted(
      [(child['name'], child['maj:min'], child['size'])
       for child in sdb_disk['children']])
  assert children == [
      ('sdb1', '8:17', '12582912'), ('sdb2', '8:18', '30408704')]


def CheckDiskHash(hash_path):
  """Checks the content of a GiftStick disk.hash file.

  Args:
    hash_path(str): path to the disk.hash file.

  Raises:
    Exception: if the input file content isn't correct.
  """
  expected = """0 - 44040192: 1e639d0a0b2c718eae71a058582a555e
0 - 44040192: 11840d13e5e9462f6acfa7bb9f700268202e29bf

Total (md5): 1e639d0a0b2c718eae71a058582a555e

Total (sha1): 11840d13e5e9462f6acfa7bb9f700268202e29bf
"""
  with open(hash_path, 'r') as hash_file:
    hash_file_content = hash_file.read()
    assert hash_file_content == expected

def CheckUdevadm(udevadm_path):
  """Checks the content of a GiftStick udevadm.txt file.

  Args:
    udevadm_path(str): path to the udevadm.txt file.

  Raises:
    Exception: if the input file content isn't correct.
  """
  expected = [
      ['DEVTYPE', 'disk'],
      ['ID_MODEL', 'QEMU_HARDDISK'],
      ['ID_SERIAL', 'QEMU_HARDDISK_QM00002']]

  with open(udevadm_path, 'r') as udevadm_file:
    udevadm_content = udevadm_file.read().splitlines()
    udevadm_pairs = [pair.split('=') for pair in udevadm_content]

    interesting_keys = ['ID_SERIAL', 'ID_MODEL', 'DEVTYPE']
    data_to_check = [pair for pair in udevadm_pairs if pair[0] in interesting_keys]

    assert data_to_check == expected

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

  check_lsblk = subparsers.add_parser(
      'check_lsblk',
      help='Checks the content of the lsblk.txt file')
  check_lsblk.add_argument(
      'lsblk', type=str, help='the lsblk.txt file to check')

  check_hash = subparsers.add_parser(
      'check_hash',
      help='Checks the content of the sdb.hash file')
  check_hash.add_argument(
      'hash', type=str, help='the sdb.hash file to check')

  check_udevadm = subparsers.add_parser(
      'check_udevadm',
      help='Checks the content of the sdb.udevadm.txt file')
  check_udevadm.add_argument(
      'udevadm', type=str, help='the sdb.udevadm.txt file to check')

  return parser.parse_args()

if __name__ == '__main__':
  options = ParseArguments()

  if options.command == 'normalize':
    print(NormalizeGCSURL(options.url))
  elif options.command == 'check_stamp':
    CheckStamp(options.stamp)
  elif options.command == 'check_system_info':
    CheckSystemInfo(options.system_info)
  elif options.command == 'check_lsblk':
    CheckLsblk(options.lsblk)
  elif options.command == 'check_hash':
    CheckDiskHash(options.hash)
  elif options.command == 'check_udevadm':
    CheckUdevadm(options.udevadm)
