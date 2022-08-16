# SPDX-License-Identifier: Apache-2.0

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError, AnsibleAction, _AnsibleActionDone, AnsibleActionFail
from ansible.module_utils._text import to_native
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.plugins.action import ActionBase
from ..callback import sanitize

class ActionModule(ActionBase):
    _VALID_ARGS = frozenset(('add',)) 
    def run(self, tmp=None, task_vars=None):
        result = super(ActionModule, self).run(tmp, task_vars)
        module_args = self._task.args.copy()

        if 'add' not in module_args:
            result['failed'] = True
            result['msg'] = "the 'add' param is required"
            return result

        if not isinstance(module_args['add'], list):
            result['failed'] = True
            result['msg'] = "the 'add' param should be list"
            return result

        client = sanitize.get_client()
        for w in module_args['add']:
            client.words().add_to_blocklist(w)
        return result
