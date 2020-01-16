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

try:
  from setuptools import find_packages, setup
except ImportError:
  from distutils.core import find_packages, setup


description = 'Forensics acquisition tool'

long_description = (
    'auto_forensicate is a module to automate uploading forensics evidence to'
    'Google Cloud Storage')

setup(
    name='auto_forensicate',
    version='20181010',
    description=description,
    long_description=long_description,
    url='https://github.com/google/giftstick',
    author='giftstick development team',
    license='Apache License, Version 2.0',
    packages=find_packages(),
    install_requires=[
        'cachetools==3.1.1',  # Because 4.0 breaks on Py2 installs
        'progress',
        'boto==2.49.0',
        'gcs_oauth2_boto_plugin',
        'google-cloud-storage',
        'google-cloud-logging'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    scripts=['auto_forensicate/auto_acquire.py']
)
