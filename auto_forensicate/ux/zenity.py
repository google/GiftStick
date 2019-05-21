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
"""Interface to Zenity."""

import subprocess


def GetText(text):
  """Ask user for a string.

  Args:
    text(str): The message to display.
  Returns:
    str: the user input.
  """

  process = subprocess.Popen(
      ['/usr/bin/zenity', '--entry', '--text="{0:s}"'.format(text)],
      stdin=subprocess.PIPE, stdout=subprocess.PIPE)

  if process.wait() == 0:
    return process.stdout.read()[:-1]

  return ''

def CheckList(column_names, data, title=None):
  """Present a list of items to select.

  Args:
    column_names(list[str]): A list containing the names of the columns.
    data(list[str]]): A list that contains, for each cell in the row,
      its selected status, and the value.
      For example: ['True', 'field1', 'False', 'Field2']
    title(str): The title of the dialog box.
  Returns:
    list[str]: the selected fields.
  """

  command = ['/usr/bin/zenity', '--list', '--checklist', '--editable=False']
  for column in column_names:
    command.append('--column="{0:s}"'.format(column))

  if title:
    command.append('--title="{0:s}"'.format(title))

  command = command + data

  process = subprocess.Popen(
      command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

  if process.wait() == 0:
    return process.stdout.read().strip().split('|')

  return []
