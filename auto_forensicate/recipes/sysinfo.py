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
"""Handles the acquisition of the system's information."""

from __future__ import unicode_literals

from auto_forensicate.recipes import base


class SysinfoRecipe(base.BaseRecipe):
  """The SysinfoRecipe class."""

  _DMI_DECODE_CMD = ['/usr/sbin/dmidecode', '--type=1']
  _SYSTEM_PROFILER_CMD = [
      '/usr/sbin/system_profiler', 'SPHardwareDataType', 'SPSoftwareDataType']

  def GetArtifacts(self):
    """Provides a list of Artifacts to upload.

    Returns:
      list(BaseArtifact): the artifacts corresponding to copy.
    """
    if self._platform == 'darwin':
      return [
          base.ProcessOutputArtifact(
              self._SYSTEM_PROFILER_CMD, 'system_info.txt')]
    return [
        base.ProcessOutputArtifact(self._DMI_DECODE_CMD, 'system_info.txt')]
