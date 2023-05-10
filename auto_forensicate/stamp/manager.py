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
"""Base Stamp classes."""

from collections import namedtuple
from auto_forensicate import hostinfo

BaseStamp = namedtuple('Stamp', ['identifier', 'start_time'])


class BaseStampManager(object):
  """Base class to generate the stamp file."""

  def __init__(self, graphical=True):
    """Initializes a BaseStampManager object.

    Args:
      graphical (bool): whether we will request information from a graphical
          environment.
    """
    self._graphical = graphical

  def BasePathElements(self, stamp):
    """Generates upload paths based on information in stamp.

    Args:
      stamp (BaseStamp): device information

    Returns:
      list(str): list of elements from the stamp
    """
    remote_path_elems = [
        stamp.start_time,
        stamp.identifier
    ]

    return remote_path_elems

  def GetStamp(self, graphical=True):
    """Generates the "stamp" metadata to upload.

    This contains information such as when the script is run, and the host's ID.
    
    Args:
      graphical(bool): Set to False if requesting the Stamp in an non-graphical
        environment.

    Returns:
      BaseStamp: the content of the stamp.
    """

    stamp = BaseStamp(
        identifier=hostinfo.GetIdentifier(),
        start_time=hostinfo.GetTime(),
    )

    return stamp
