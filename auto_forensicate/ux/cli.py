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
"""Function to interact with the user in a console environment."""


def AskText(message, mandatory=False):
  """Asks a question.

  Args:
    message(str): the question.
    mandatory(bool): whether the answer can be left empty.

  Returns:
    str: the user's answer to the question.
  """
  print(message)
  text = input()
  if mandatory and not text:
    while not text:
      text = input()
  # TODO: Sanitize input here, as this will be used to construct GCS paths.
  return text.decode()


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


  valid_choice = False
  disk_indices_to_copy = [i for i, disk in enumerate(disk_list) if disk.ProbablyADisk()]
  while not valid_choice:
    print('\nPlease select which disks to copy:')
    for num, disk in enumerate(disk_list, start=0):
      print('{0:d}\t{1:s}'.format(num, disk.GetDescription()))
      user_choices = input(
        'Disk numbers (Default is [{0:s}], comma separated): '.format(
            ','.join([str(i) for i in disk_indices_to_copy])))
    if user_choices == "":
      valid_choice = True
    else:
      choices = user_choices.replace(' ', ',').split(',')
      try:
        choices = list(map(int, choices))
      except ValueError:
        continue
      if all([0 <= int(i) and int(i) < len(disk_list) for i in choices]):
        valid_choice = True
        disk_indices_to_copy = list(set(choices)) # Removing doubles

  print(disk_indices_to_copy)
  return [disk for index, disk in enumerate(disk_list, start=0) if index in disk_indices_to_copy]


def Confirm(text):
  """Asks the user to confirm something.

  Args:
    text(str): the text of the question.
  Returns:
    bool: True if the user confirms, False otherwise.
  """
  return zenity.GetYesNo(text)
