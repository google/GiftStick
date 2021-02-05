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
"""Installation and deployment script."""

import pkg_resources
from setuptools import find_packages
from setuptools import setup


def ParseRequirements(filename):
  """Parse python requirements.

  Args:
    filename (str): The requirement file to read.
  Returns:
    List[str]: a list of requirements.
  """
  install_requires = []
  with open(filename) as requirements:
    install_requires = [
        str(requirement) for requirement in
        pkg_resources.parse_requirements(requirements)]

  return install_requires


description = 'Forensics acquisition tool'

long_description = (
    'auto_forensicate is a module to automate uploading forensics evidence to'
    'Google Cloud Storage')

setup(
    name='auto_forensicate',
    version='20210201',
    description=description,
    long_description=long_description,
    url='https://github.com/google/giftstick',
    author='giftstick development team',
    license='Apache License, Version 2.0',
    packages=find_packages(),
    install_requires=ParseRequirements('requirements.txt'),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    scripts=['auto_forensicate/auto_acquire.py']
)
