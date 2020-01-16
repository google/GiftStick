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

from auto_forensicate import hostinfo
from auto_forensicate.recipes import base


class SysinfoRecipe(base.BaseRecipe):
  """The SysinfoRecipe class."""

  def GetArtifacts(self):
    """Provides a list of Artifacts to upload.

    Returns:
      list(BaseArtifact): the artifacts to copy.
    """
    artifacts_list = []
    if self._platform == 'darwin':
      system_profiler_cmd = [
          # TODO: have hostinfo.Which work on darwin
          '/usr/sbin/system_profiler', 'SPHardwareDataType',
          'SPSoftwareDataType']
      artifacts_list.append(
          base.ProcessOutputArtifact(system_profiler_cmd, 'system_info.txt'))
    else:
      dmidecode_path = hostinfo.Which('dmidecode')
      dmidecode_cmd = [dmidecode_path, '--type=1']
      artifacts_list.append(
          base.ProcessOutputArtifact(dmidecode_cmd, 'system_info.txt'))
