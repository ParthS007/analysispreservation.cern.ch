# -*- coding: utf-8 -*-
#
# This file is part of CERN Analysis Preservation Framework.
# Copyright (C) 2017 CERN.
#
# CERN Analysis Preservation Framework is free software; you can redistribute
# it and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# CERN Analysis Preservation Framework is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CERN Analysis Preservation Framework; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.
"""Experiment validators methods."""

from jsonschema.exceptions import ValidationError

from .search.cms_triggers import CMSTriggerSearch
from .search.das import DASSearch
from cap.modules.deposit.errors import (DepositDoesNotExist,
                                        UniqueRequiredValidationError)


def validate_cms_trigger(validator, value, instance, schema):
    errors = []
    path = instance.get('path')
    year = instance.get('year')
    for index, trigger in enumerate(instance.get('triggers', [])):
        search = CMSTriggerSearch().exact_search(trigger['trigger'], path,
                                                 year)
        if search.count() == 0:
            errors.append({
                "message":
                "{} is not a valid trigger for this dataset.".format(
                    trigger['trigger']),
                "path": ["triggers", index, "trigger"]
            }),

    for error in errors:
        yield ValidationError(**error)


def validate_das_path(validator, value, instance, schema):
    search = DASSearch().exact_search(instance)

    if search.count() == 0:
        yield ValidationError("{} not found in DAS.".format(instance))


def validate_cadi_id(validator, value, instance, schema):
    from .utils.cadi import get_from_cadi_by_id
    if not get_from_cadi_by_id(instance, from_validator=True):
        yield ValidationError("{} not found in CADI.".format(instance))


def validate_unique_cadi(validator, value, instance, schema):
    from .utils.cadi import get_uuids_with_same_cadi_id
    try:
        uuids = get_uuids_with_same_cadi_id(instance)
        yield UniqueRequiredValidationError(
            "This ID is already attached to another record", uuids=uuids)
    except DepositDoesNotExist:
            pass
