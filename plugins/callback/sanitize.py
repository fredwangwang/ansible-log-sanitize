# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, division, print_function)
import os

from ansible.plugins.loader import callback_loader
from ansible.utils.color import colorize, hostcolor
from ansible.plugins.callback import CallbackBase
from ansible.playbook.task_include import TaskInclude
from ansible import context
from ansible import constants as C
from multiprocessing.managers import BaseManager
from threading import Lock

DOCUMENTATION = '''
    callback: sanitize
    type: stdout
    short_description: Ansible sanitized screen output
    description:
        - This is the output callback for ansible-playbook that can selectively filter out keywords.
    requirements:
      - set as stdout in configuration
    options:
      style:
        description: The underlying output pluging format to use
        default: default
        env:
          - name: SANITIZE_STYLE
        ini:
          - section: callback_sanitize
            key: style
      blocklist:
        description: The default list to block
        default: []
        type: list
        env:
          - name: SANITIZE_BLOCKLIST
        ini:
          - section: callback_sanitize
            key: blocklist
'''

authkey = os.urandom(20)
if os.name == 'nt':
    address = r'\.\pipesanitizewordsmgr'
else:
    address = '/tmp/sanitizewordsmgr.sock'


class Words:
    '''
    the shared object thats proxied by manager.
    Once the manager starts it runs the listener/accepter in a separate process with multi-thread.
    in case multiple ansible tasks are running (e.g. ansible --forks 20) and calls sanitize_ctl
    at the same time, there would be data race at the manager process when multiple thread trying
    to write to shard set. Thus needing the thread locks to guard the critical section.
    '''
    _s = set()
    _l = Lock()

    def add_to_blocklist(self, w):
        Words._l.acquire()
        Words._s.add(w)
        Words._l.release()

    def get_blocklist(self):
        Words._l.acquire()
        res = Words._s.copy()
        Words._l.release()
        return res


class WordsManager(BaseManager):
    '''
    the manager class that proxies the words object to the multiprocess spawned by ansible executor.
    So that the sanitize_ctl module can update the word list during runtime.
    '''


WordsManager.register('words', Words)
mgr = WordsManager(address=address, authkey=authkey)


def get_client():
    mgr.connect()
    return mgr


def sanitize(res):
    for k in mgr.words().get_blocklist():
        res = res.replace(k, '*****')
    return res


class CallbackModule(CallbackBase):
    '''
    This is the sanitize callback interface, uses the underlying cb as defined by style
    and then sanitize the sensitive information before printing to screen.
    '''

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'sanitize'

    def __init__(self):
        self.finished_setup = False
        self.cb_plugin = None
        self.old_dump_results = None

        super(CallbackModule, self).__init__()
        mgr.start()

    def set_options(self, *args, **kvargs):
        super(CallbackModule, self).set_options(*args, **kvargs)

        # init underlying callback plugin
        blocklist = self.get_option('blocklist')
        for w in blocklist:
            mgr.words().add_to_blocklist(w)
        style = self.get_option('style')
        cb_plugin = callback_loader.get(style)
        cb_plugin.set_options(*args, **kvargs)

        # patch dump result call
        if not cb_plugin._dump_results:
            raise RuntimeError("the callback plugn does not implement _dump_results. "
                               "This might due to an ansible version change, and the plugin WILL NOT sanitize the output as expected. "
                               "Please fix the sanitize plugin to patch the correct method.")

        self.old_dump_results = cb_plugin._dump_results
        cb_plugin._dump_results = self.sanitized_dump_results

        self.cb_plugin = cb_plugin

        self.finished_setup = True

    def sanitized_dump_results(self, *args, **kvargs):
        res = self.old_dump_results(*args, **kvargs)
        return sanitize(res)

    def __getattribute__(self, name: str):
        if not object.__getattribute__(self, 'finished_setup'):
            # before self is fully initialized, route all calls to self.
            return object.__getattribute__(self, name)

        # after self fully initialized, route selective call to self and all other to underlying cb
        if name in ['finished_setup',
                    'cb_plugin',
                    'old_dump_results',
                    'sanitized_dump_results']:
            return object.__getattribute__(self, name)
        return self.cb_plugin.__getattribute__(name)
