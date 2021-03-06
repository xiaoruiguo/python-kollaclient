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
import argparse
import getpass
import logging
import traceback

from cliff.command import Command
from cliff.lister import Lister

from kollacli.ansible.passwords import clear_password
from kollacli.ansible.passwords import get_password_names
from kollacli.ansible.passwords import set_password


class PasswordSet(Command):
    "Password Set"

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(PasswordSet, self).get_parser(prog_name)
        parser.add_argument('passwordname', metavar='<passwordname>',
                            help='passwordname')
        parser.add_argument('--insecure', nargs='?', help=argparse.SUPPRESS)
        return parser

    def take_action(self, parsed_args):
        try:
            password_name = parsed_args.passwordname.strip()
            if parsed_args.insecure:
                password = parsed_args.insecure.strip()
            else:
                password = getpass.getpass('Password: ').strip()

            set_password(password_name, password)

        except Exception:
            raise Exception(traceback.format_exc())


class PasswordClear(Command):
    "Password Clear"

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(PasswordClear, self).get_parser(prog_name)
        parser.add_argument('passwordname', metavar='<passwordname>',
                            help='passwordname')
        return parser

    def take_action(self, parsed_args):
        try:
            password_name = parsed_args.passwordname.strip()
            clear_password(password_name)
        except Exception:
            raise Exception(traceback.format_exc())


class PasswordList(Lister):
    """List all password names"""

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        password_names = get_password_names()
        password_names = sorted(password_names)

        data = []
        for password_name in password_names:
            data.append((password_name, '-'))

        return (('Password Name',  'Password'), data)
