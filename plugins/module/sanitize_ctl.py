# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: sanitize_ctl
short_description: Update the blocked message
description:
- This module controls log_sanitize blocklist
options:
  add:
    description:
    - Add the list of words to blocklists
    type: list
'''

EXAMPLES = r'''
- sanitize_ctl:
    add: ['myPassw0rd']
'''
