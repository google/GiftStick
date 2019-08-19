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

from auto_forensicate.ux import zenity


def AskText(message, mandatory=False):
  """Pops up a UI window asking a question.

  Args:
    message(str): the question.
    mandatory(bool): whether the answer can be left empty.

  Returns:
    str: the user's answer to the question.
  """
  text = zenity.GetText(message)
  if mandatory and not text:
    while not text:
      text = zenity.GetText(message)
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

  data = []
  for disk in disk_list:
    # Default is to un-check block devices that are not internal disks.
    data.append(str(disk.ProbablyADisk()))
    data.append(disk.GetDescription())

  choices = []
  while not choices:
    choices = zenity.CheckList(
        ['', 'Disks'],
        title='Please select which disks to copy.',
        data=data
    )

  if choices == ['']:
    return []
  return [disk_description_map[choice] for choice in choices]


def Confirm(text):
  """Asks the user to confirm something.

  Args:
    text(str): the text of the question.
  Returns:
    bool: True if the user confirms, False otherwise.
  """
  return zenity.GetYesNo(text)
