# Copyright(c) 2015, Oracle and/or its affiliates.  All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import logging
import os
import tarfile
import tempfile
import traceback

from kollacli.ansible.inventory import Inventory
from kollacli.ansible.playbook import AnsiblePlaybook
from kollacli.ansible.properties import AnsibleProperties
from kollacli.exceptions import CommandError
from kollacli.utils import convert_to_unicode
from kollacli.utils import get_kolla_etc
from kollacli.utils import get_kolla_home
from kollacli.utils import get_kolla_log_dir
from kollacli.utils import get_kollacli_etc
from kollacli.utils import run_cmd

from cliff.command import Command


class Deploy(Command):
    """Deploy"""

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(Deploy, self).get_parser(prog_name)
        parser.add_argument('--hosts', nargs='?',
                            metavar='<host_list>',
                            help='deployment host list')
        parser.add_argument('--groups', nargs='?',
                            metavar='<group_list>',
                            help='deployment group list')
        parser.add_argument('--services', nargs='?',
                            metavar='<service_list>',
                            help='deployment service list')
        parser.add_argument('--serial', action='store_true',
                            help='deploy serially')
        return parser

    def take_action(self, parsed_args):
        try:
            if parsed_args.hosts and parsed_args.groups:
                raise CommandError('Hosts and Groups arguments cannot both ' +
                                   'be present at the same time.')

            self._run_rules()

            playbook = AnsiblePlaybook()
            kolla_home = get_kolla_home()
            playbook.playbook_path = os.path.join(kolla_home,
                                                  'ansible/site.yml')
            if parsed_args.hosts:
                host_list = parsed_args.hosts.strip()
                host_list = convert_to_unicode(host_list)
                playbook.hosts = host_list.split(',')
            if parsed_args.groups:
                group_list = parsed_args.groups.strip()
                group_list = convert_to_unicode(group_list)
                playbook.groups = group_list.split(',')
            if parsed_args.services:
                tag_list = parsed_args.services.strip()
                tag_list = convert_to_unicode(tag_list)
                playbook.services = tag_list.split(',')
            if parsed_args.serial:
                playbook.serial = True

            playbook.verbose_level = self.app.options.verbose_level
            playbook.run()
        except CommandError as e:
            raise e
        except Exception:
            raise Exception(traceback.format_exc())

    def _run_rules(self):
        # check that ring files are in /etc/kolla/config/swift if
        # swift is enabled
        expected_files = ['account.ring.gz',
                          'container.ring.gz',
                          'object.ring.gz']
        properties = AnsibleProperties()
        is_enabled = properties.get_property('enable_swift')
        if is_enabled == 'yes':
            path_pre = os.path.join(get_kolla_etc(), 'config', 'swift')
            for expected_file in expected_files:
                path = os.path.join(path_pre, expected_file)
                if not os.path.isfile(path):
                    msg = ('Deploy failed. ' +
                           'Swift is enabled but ring buffers have ' +
                           'not yet been set up. Please see the ' +
                           'documentation for swift configuration ' +
                           'instructions.')
                    raise CommandError(msg)


class Dump(Command):
    """Dumps configuration data for debugging

    Dumps most files in /etc/kolla and /usr/share/kolla into a
    tar file so be given to support / development to help with
    debugging problems.
    """
    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        try:
            kolla_home = get_kolla_home()
            kolla_logs = get_kolla_log_dir()
            kolla_ansible = os.path.join(kolla_home, 'ansible')
            kolla_docs = os.path.join(kolla_home, 'docs')
            kolla_etc = get_kolla_etc()
            kolla_config = os.path.join(kolla_etc, 'config')
            kolla_globals = os.path.join(kolla_etc, 'globals.yml')
            kollacli_etc = get_kollacli_etc().rstrip('/')
            ketc = 'kolla/etc/'
            kshare = 'kolla/share/'
            fd, dump_path = tempfile.mkstemp(prefix='kollacli_dump_',
                                             suffix='.tgz')
            os.close(fd)  # avoid fd leak
            with tarfile.open(dump_path, 'w:gz') as tar:
                # Can't blanket add kolla_home because the .ssh dir is
                # accessible by the kolla user only (not kolla group)
                tar.add(kolla_ansible,
                        arcname=kshare + os.path.basename(kolla_ansible))
                tar.add(kolla_docs,
                        arcname=kshare + os.path.basename(kolla_docs))

                # Can't blanket add kolla_etc because the passwords.yml
                # file is accessible by the kolla user only (not kolla group)
                tar.add(kolla_config,
                        arcname=ketc + os.path.basename(kolla_config))
                tar.add(kolla_globals,
                        arcname=ketc + os.path.basename(kolla_globals))
                tar.add(kollacli_etc,
                        arcname=ketc + os.path.basename(kollacli_etc))

                # add kolla log files
                if os.path.isdir(kolla_logs):
                    tar.add(kolla_logs)

                # add output of various commands
                self._add_cmd_info(tar)

            self.log.info('dump successful to %s' % dump_path)
        except Exception:
            raise Exception(traceback.format_exc())

    def _add_cmd_info(self, tar):
        # run all the kollacli list commands
        cmds = ['kollacli service listgroups',
                'kollacli service list',
                'kollacli group listservices',
                'kollacli group listhosts',
                'kollacli host list',
                'kollacli property list',
                'kollacli password list']

        # collect the json inventory output
        inventory = Inventory.load()
        inv_path = inventory.create_json_gen_file()
        cmds.append(inv_path)

        try:
            fd, path = tempfile.mkstemp(suffix='.tmp')
            os.close(fd)
            with open(path, 'w') as tmp_file:
                for cmd in cmds:
                    err_msg, output = run_cmd(cmd, False)
                    tmp_file.write('\n\n$ %s\n' % cmd)
                    if err_msg:
                        tmp_file.write('Error message: %s\n' % err_msg)
                    lines = output.split('\n')
                    for line in lines:
                        tmp_file.write(line + '\n')
            tar.add(path, arcname=os.path.join('kolla', 'cmds_output'))

        except Exception as e:
            raise e
        finally:
            if path:
                os.remove(path)
            if inv_path:
                os.remove(inv_path)
        return


class Setdeploy(Command):
    """Set deploy mode

    Set deploy mode to either local or remote. Local indicates
    that the openstack deployment will be to the local host.
    Remote means that the deployment is on remote hosts.
    """
    def get_parser(self, prog_name):
        parser = super(Setdeploy, self).get_parser(prog_name)
        parser.add_argument('mode', metavar='<mode>',
                            help='mode=<local, remote>')
        return parser

    def take_action(self, parsed_args):
        try:
            mode = parsed_args.mode.strip()
            remote_flag = False
            if mode == 'remote':
                remote_flag = True
            elif mode != 'local':
                raise CommandError('Invalid deploy mode. Mode must be ' +
                                   'either "local" or "remote"')
            inventory = Inventory.load()
            inventory.set_deploy_mode(remote_flag)
            Inventory.save(inventory)
        except CommandError as e:
            raise e
        except Exception:
            raise Exception(traceback.format_exc())
