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
"""Handles the acquisition of the system's firmware."""

from __future__ import unicode_literals

from auto_forensicate.recipes import base


class ChipsecRecipe(base.BaseRecipe):
  """The ChipsecRecipe class, which acquires the system's Firmware."""

  _CHIPSEC_CMD = [
      'chipsec_util', '-l', '/dev/stderr', 'spi', 'dump', '/dev/stdout']

  def GetArtifacts(self):
    """Provides a list of Artifacts to upload.

    Returns:
      list(BaseArtifact): the artifacts for the system's firmware.
    """
    if self._platform == 'darwin':
      self._logger.info('Firmware acquisition only works on Linux, skipping.')
      return []

    # Firmware acquisition will fail on various platforms (ie: QEMU during e2e
    # tests, and shouldn't be a reason to mark the full upload as failed.
    # So we're setting ignore_failure to True.
    firmware_artifact = base.ProcessOutputArtifact(
        self._CHIPSEC_CMD, 'Firmware/rom.bin', ignore_failure=True)
    return [firmware_artifact]
