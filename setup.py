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

import unittest


description = 'Forensics acquisition tool'

long_description = (
    'auto_forensicate is a module to automate uploading forensics evidence to'
    'Google Cloud Storage')

def test_suite():
  """Loads the unittest suite."""
  loader = unittest.TestLoader()
  start_dir = 'tests'
  suite = loader.discover(start_dir, pattern='*_tests.py')
  return suite


setup(
    name='auto_forensicate',
    version='20181010',
    description=description,
    long_description=long_description,
    url='https://github.com/google/giftstick',
    author='giftstick development team',
    license='Apache License, Version 2.0',
    packages=find_packages(exclude=['tests']),
    dependency_links=[
        'http://brianramos.com/software/PyZenity/PyZenity-0.1.8.tar.gz'
        '#egg=PyZenity-0.1.8'],
    install_requires=[
        'progressbar',
        'boto',
        'gcs_oauth2_boto_plugin',
        'google-cloud-storage',
        'google-cloud-logging',
        'PyZenity'
    ],
    tests_require=['mock', 'PyZenity', 'boto', 'google-cloud-logging'],
    test_suite='setup.test_suite',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    scripts=['auto_forensicate/auto_acquire.py']
)
