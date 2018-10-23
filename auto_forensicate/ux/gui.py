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
"""Function to interact with the user in a graphic environment."""

import PyZenity


def AskText(message, mandatory=False):
  """Pops up a UI window asking a question.

  Args:
    message(str): the question.
    mandatory(bool): whether the answer can be left empty.

  Returns:
    str: the user's answer to the question.
  """
  text = PyZenity.GetText(message)
  if mandatory and not text:
    while not text:
      text = PyZenity.GetText(message)
  # TODO: Sanitize input here, as this will be used to construct GCS paths.
  return text


def AskDiskList(disk_list):
  """Asks the user to select which disk to copy.

  Args:
    disk_list(DiskArtifact): list of disks.

  Returns:
    list(DiskArtifact): a list of devices.
  """
  disk_description_map = dict(
      zip(
          [disk.GetDescription() for disk in disk_list],
          [disk for disk in disk_list],
      )
  )

  data = [
      (
          # Default is to un-check block devices that are not internal disks.
          disk.ProbablyADisk(),
          disk.GetDescription()
      ) for disk in disk_list]
  choices = []
  while not choices:
    choices = PyZenity.List(
        ['', 'Disks'],
        title='Please select which disks to copy.',
        boolstyle='checklist',
        editable=False,
        data=data
    )

  if choices == ['']:
    return []
  return [disk_description_map[choice] for choice in choices]

