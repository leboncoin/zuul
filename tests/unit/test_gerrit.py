# Copyright 2015 BMW Car IT GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os
from unittest import mock

import tests.base
from tests.base import BaseTestCase, ZuulTestCase, AnsibleZuulTestCase
from zuul.driver.gerrit import GerritDriver
from zuul.driver.gerrit.gerritconnection import GerritConnection

FIXTURE_DIR = os.path.join(tests.base.FIXTURE_DIR, 'gerrit')


def read_fixture(file):
    with open('%s/%s' % (FIXTURE_DIR, file), 'r') as fixturefile:
        lines = fixturefile.readlines()
        command = lines[0].replace('\n', '')
        value = ''.join(lines[1:])
        return command, value


def read_fixtures(files):
    calls = []
    values = []
    for fixture_file in files:
        command, value = read_fixture(fixture_file)
        calls.append(mock.call(command))
        values.append([value, ''])
    return calls, values


class TestGerrit(BaseTestCase):

    @mock.patch('zuul.driver.gerrit.gerritconnection.GerritConnection._ssh')
    def run_query(self, files, expected_patches, _ssh_mock):
        gerrit_config = {
            'user': 'gerrit',
            'server': 'localhost',
        }
        driver = GerritDriver()
        gerrit = GerritConnection(driver, 'review_gerrit', gerrit_config)

        calls, values = read_fixtures(files)
        _ssh_mock.side_effect = values

        result = gerrit.simpleQuery('project:openstack-infra/zuul')

        _ssh_mock.assert_has_calls(calls)
        self.assertEqual(len(calls), _ssh_mock.call_count,
                         '_ssh should be called %d times' % len(calls))
        self.assertIsNotNone(result, 'Result is not none')
        self.assertEqual(len(result), expected_patches,
                         'There must be %d patches.' % expected_patches)

    def test_simple_query_pagination_new(self):
        files = ['simple_query_pagination_new_1',
                 'simple_query_pagination_new_2']
        expected_patches = 5
        self.run_query(files, expected_patches)

    def test_simple_query_pagination_old(self):
        files = ['simple_query_pagination_old_1',
                 'simple_query_pagination_old_2',
                 'simple_query_pagination_old_3']
        expected_patches = 5
        self.run_query(files, expected_patches)


class TestGerritWeb(ZuulTestCase):
    config_file = 'zuul-gerrit-web.conf'
    tenant_config_file = 'config/single-tenant/main.yaml'

    def test_jobs_executed(self):
        "Test that jobs are executed and a change is merged"
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()
        self.assertEqual(self.getJobFromHistory('project-merge').result,
                         'SUCCESS')
        self.assertEqual(self.getJobFromHistory('project-test1').result,
                         'SUCCESS')
        self.assertEqual(self.getJobFromHistory('project-test2').result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(self.getJobFromHistory('project-test1').node,
                         'label1')
        self.assertEqual(self.getJobFromHistory('project-test2').node,
                         'label1')


class TestFileComments(AnsibleZuulTestCase):
    # A temporary class to hold new tests while others are disabled
    config_file = 'zuul-gerrit-web.conf'
    tenant_config_file = 'config/gerrit-file-comments/main.yaml'

    def test_multiple_tenants(self):
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.assertEqual(self.getJobFromHistory('file-comments').result,
                         'SUCCESS')
        self.assertEqual(len(A.comments), 3)
        comments = sorted(A.comments, key=lambda x: x['line'])
        self.assertEqual(comments[0],
                         {'file': 'otherfile.txt',
                          'line': 21,
                          'message': 'This is a much longer message.\n\n'
                          'With multiple paragraphs.\n',
                          'reviewer': {'email': 'zuul@example.com',
                                       'name': 'Zuul',
                                       'username': 'jenkins'}}
        )
        self.assertEqual(comments[1],
                         {'file': 'path/to/file.py',
                          'line': 42,
                          'message': 'line too long',
                          'reviewer': {'email': 'zuul@example.com',
                                       'name': 'Zuul',
                                       'username': 'jenkins'}}
        )
        self.assertEqual(comments[2],
                         {'file': 'path/to/file.py',
                          'line': 82,
                          'message': 'line too short',
                          'reviewer': {'email': 'zuul@example.com',
                                       'name': 'Zuul',
                                       'username': 'jenkins'}}
        )
