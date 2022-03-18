# -*- coding: utf-8 -*-
#
# This file is part of CERN Analysis Preservation Framework.
# Copyright (C) 2018 CERN.
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
"""CAP REANA views."""

from io import BytesIO
from functools import wraps
from coolname import generate_slug
from jsonschema.exceptions import ValidationError
from flask import Blueprint, jsonify, request, abort
from flask_login import current_user

from reana_client.api.client import (
    ping, get_workflow_status, start_workflow, get_workflow_logs,
    create_workflow, delete_workflow, stop_workflow, delete_file, list_files,
    download_file, upload_file)
from reana_client.errors import FileDeletionError, FileUploadError
from reana_client.utils import load_reana_spec

from .models import ReanaWorkflow
from .utils import (update_workflow, clone_workflow, get_reana_token,
                    resolve_uuid, resolve_depid, update_deposit_workflow)
from .serializers import ReanaWorkflowLogsSchema

from cap.modules.access.utils import login_required
from cap.modules.records.api import CAPRecord
from cap.modules.deposit.api import CAPDeposit
from cap.modules.experiments.errors import ExternalAPIException

workflows_bp = Blueprint('cap_workflows', __name__, url_prefix='/workflows')


def pass_workflow(with_access=False, with_record=False, with_token=False):
    def _pass_workflow(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            workflow_id = kwargs.get('workflow_id', None)

            if workflow_id:
                workflow = ReanaWorkflow.get_workflow_by_id(workflow_id)

                if with_access:
                    if workflow.user_id == current_user.id:
                        if with_record:
                            deposit = CAPRecord.get_record(workflow.rec_uuid)
                            if deposit:
                                if with_token:
                                    token = get_reana_token(record=deposit)
                                    if token:
                                        return f(*args,
                                                 workflow=workflow,
                                                 deposit=deposit,
                                                 token=token,
                                                 **kwargs)
                                    else:
                                        return abort(404)
                                return f(*args,
                                         workflow=workflow,
                                         deposit=deposit,
                                         **kwargs)
                            else:
                                return abort(404)
                        return f(*args, workflow=workflow, **kwargs)
                    else:
                        return abort(403)

                return f(*args, workflow=workflow, **kwargs)

        return wrapper

    return _pass_workflow


@workflows_bp.route('/reana/ping')
@login_required
def ping_reana():
    """Ping the service."""
    try:
        resp = ping()
        status = 200 if resp == 'OK' else 400
        return jsonify({'message': resp}), status
    except Exception:
        raise ExternalAPIException()


@workflows_bp.route('/reana/validate', methods=['POST'])
@login_required
def validate_reana_workflow_spec():
    """Validate workflow specification file."""
    _args = request.get_json()
    _, rec_uuid = resolve_depid(_args.get('pid'))
    deposit = CAPRecord.get_record(rec_uuid)
    spec_files = _args.get('files_to_validate')

    token = get_reana_token(rec_uuid)
    errors = {}
    validated = []

    for _f in spec_files:
        file_path = deposit.files[_f['path']].obj.file.uri
        try:
            load_reana_spec(file_path, access_token=token)
            validated.append(_f['path'])
        except ValidationError as e:
            errors[_f['path']] = e.message

    return jsonify({
        'validated': validated,
        'errors': errors
    }), 200


@workflows_bp.route('/', methods=['GET'])
@login_required
def get_workflows_view():
    """Get all workflows of a single user."""
    workflows = ReanaWorkflow.get_user_workflows(current_user.id)

    _workflows = [workflow.serialize() for workflow in workflows]
    return jsonify(_workflows)


@workflows_bp.route('/all/record/<depid>')
@login_required
def get_all_reana_workflows(depid):
    """Get all workflows for a single experiment."""
    _, rec_uuid = resolve_depid(depid)
    workflows = ReanaWorkflow.get_deposit_workflows(rec_uuid)
    _workflows = [workflow.serialize() for workflow in workflows]
    return jsonify(_workflows)


@workflows_bp.route('/reana', methods=['POST'])
@login_required
def create_reana_workflow():
    """Create a reana workflow by json."""
    _args = request.get_json()
    name = _args.get('workflow_name')
    workflow_json = _args.get('workflow_json')
    workflow_name = generate_slug(2)

    _, rec_uuid = resolve_depid(_args.get('pid'))
    deposit = CAPRecord.get_record(rec_uuid)
    token = get_reana_token(rec_uuid)

    # Create workflow
    try:
        resp = create_workflow(workflow_json, workflow_name, token)
    except ValidationError as e:
        return jsonify({'message': e.message}), 400
    except Exception:
        return jsonify({
            'message':
            'An exception has occured while creating '
            'the workflow in REANA.'
        }), 400

    if resp:
        workflow = update_deposit_workflow(deposit, current_user, name, workflow_name,
                                           resp, rec_uuid, workflow_json)
    return jsonify(workflow)


@workflows_bp.route('/reana/<workflow_id>')
@login_required
@pass_workflow(with_access=True)
def get_workflow(workflow_id, workflow=None):
    """Clone a workflow by returning the parameters of the original."""
    return jsonify(workflow.serialize())


@workflows_bp.route('/reana/<workflow_id>/clone')
@login_required
@pass_workflow(with_access=True)
def clone_reana_workflow(workflow_id, workflow=None):
    """Clone a workflow by returning the parameters of the original."""
    try:
        resp = clone_workflow(workflow_id)
        return jsonify(resp)
    except Exception:
        return jsonify({
            'message': ('An exception has occured while retrieving '
                        'the original workflow attributes.')
        }), 400


@workflows_bp.route('/reana/<workflow_id>/status')
@login_required
@pass_workflow(with_access=True)
def get_reana_workflow_status(workflow_id, workflow=None):
    """Get the status of a workflow."""
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)
    resp = get_workflow_status(workflow_id, token)

    update_workflow(workflow_id, 'status', resp['status'])
    return jsonify(resp)


@workflows_bp.route('/reana/<workflow_id>/logs')
@login_required
@pass_workflow(with_access=True)
def get_reana_workflow_logs(workflow_id, workflow=None):
    """Get the logs of a workflow."""
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    resp = get_workflow_logs(workflow_id, token)

    # logs = resp.get('logs', '')

    resp.update({'rec_uuid': rec_uuid})
    logs_serialized = ReanaWorkflowLogsSchema().dump(resp).data

    update_workflow(workflow_id, 'logs', logs_serialized)
    return jsonify(logs_serialized)


@workflows_bp.route('/reana/<workflow_id>/start', methods=['POST'])
@workflows_bp.route('/reana/<workflow_id>/restart', methods=['POST'])
@login_required
@pass_workflow(with_access=True)
def start_reana_workflow(workflow_id, workflow=None):
    """Start/Restart a REANA workflow.

    For restarting: `parameters` should have {"restart": True}
    """
    _args = request.get_json()
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)
    parameters = _args.get('parameters')

    try:
        resp = start_workflow(workflow_id, token, parameters)
        update_workflow(workflow_id, 'status', resp['status'])
        return jsonify(resp)
    except Exception:
        return jsonify({
            'message':
            'An exception has occured, most probably '
            'the workflow cannot start/restart.'
        }), 400


@workflows_bp.route('/reana/run', methods=['POST'])
@login_required
def run_reana_workflow():
    """Create a new workflow using json, upload files and start the workflow."""
    _args = request.get_json()
    name = _args.get('workflow_name')
    workflow_name = generate_slug(2)
    workflow_json = _args.get('workflow_json')
    parameters = _args.get('parameters')
    files = _args.get('files_to_upload')

    _, rec_uuid = resolve_depid(_args.get('pid'))
    deposit = CAPRecord.get_record(rec_uuid)
    token = get_reana_token(rec_uuid)

    # Create workflow
    try:
        resp = create_workflow(workflow_json, workflow_name, token)
    except ValidationError as e:
        return jsonify({'message': e.message}), 400
    except Exception:
        return jsonify({
            'message':
            'An exception has occured while creating '
            'the workflow in REANA.'
        }), 400

    if resp:
        workflow = update_deposit_workflow(deposit, current_user, name, workflow_name,
                                           resp, rec_uuid, workflow_json)

    # Upload files
    if files:
        for _f in files:
            file_path = deposit.files[_f['path']].obj.file.uri
            try:
                with open(file_path, 'rb') as content:
                    upload_file(workflow.get('workflow_id'),
                                content, _f['new_path'], token)
            except (IOError, FileUploadError) as e:
                return jsonify({
                    'message':
                    'An exception occured while '
                    'uploading file {}: {}'.format(_f, e)
                }), 400

    # Start workflow
    try:
        resp = start_workflow(workflow.get('workflow_id'), token, parameters)
        update_workflow(workflow.get('workflow_id'), 'status', resp['status'])
        return jsonify(resp)
    except Exception:
        return jsonify({
            'message':
            'An exception has occured, most probably '
            'the workflow cannot start/restart.'
        }), 400


@workflows_bp.route('/reana/<workflow_id>/stop', methods=['POST'])
@login_required
@pass_workflow(with_access=True)
def stop_reana_workflow(workflow_id, workflow=None):
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    try:
        resp = stop_workflow(workflow_id, True, token)
        update_workflow(workflow_id, 'status', 'stopped')
        return jsonify(resp)
    except Exception:
        return jsonify({
            'message':
            'An exception has occured, most probably '
            'the workflow is not running.'
        }), 400


@workflows_bp.route('/reana/<workflow_id>', methods=['DELETE'])
@login_required
@pass_workflow(with_access=True)
def delete_reana_workflow(workflow_id, workflow=None):
    """Delete a workflow."""
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    try:
        # all_runs and workspace
        resp = delete_workflow(workflow_id, True, True, token)
        update_workflow(workflow_id, 'status', 'deleted')
        return jsonify(resp)
    except Exception:
        return jsonify({
            'message':
            'Workflow {} does not exist. Aborting '
            'deletion.'.format(workflow_id)
        }), 400


@workflows_bp.route('/reana/<workflow_id>/files')
@login_required
@pass_workflow(with_access=True)
def list_reana_workflow_files(workflow_id, workflow=None):
    """Show the files of a workflow."""
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    try:
        resp = list_files(workflow_id, token)
        _files = {
            'rec_uuid': rec_uuid,
            'workflow_id': workflow_id,
            'files': resp
        }
        return jsonify(_files)
    except Exception:
        return jsonify({
            'message':
            'File list from workflow {} could not be '
            'retrieved. Aborting listing.'.format(workflow_id)
        }), 400


@workflows_bp.route('/reana/<workflow_id>/files/<path:path>', methods=['GET'])
@login_required
@pass_workflow(with_access=True)
def download_reana_workflow_files(workflow_id, path=None, workflow=None):
    """Download files from a workflow and save in deposit."""
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    deposit = CAPDeposit.get_record(rec_uuid)
    try:
        resp, file_name = download_file(workflow_id, path, token)
    except Exception:
        return jsonify({
            'message':
            '{} did not match any existing file. '
            'Aborting download.'.format(path)
        }), 400

    # Convert the response in buffer stream
    file = BytesIO(resp)
    size = len(resp)

    try:
        deposit.save_file(file, file_name, size)
        return jsonify({
            'message': 'File {} successfully saved '
            'in the deposit.'.format(file_name)
        }), 200
    except Exception as e:
        return jsonify({
            'message':
            '{} occured while saving the file '
            'in the deposit.'.format(e)
        }), 400


@workflows_bp.route('/reana/<workflow_id>/files/upload', methods=['POST'])
@login_required
@pass_workflow(with_access=True, with_record=True)
def upload_reana_workflow_files(workflow_id, workflow=None, deposit=None):
    """Upload files to a workflow."""
    _args = request.get_json()
    files = _args.get('files_to_upload')

    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    errors = []
    successful = []
    for _f in files:
        file_path = deposit.files[_f['path']].obj.file.uri
        try:
            with open(file_path, 'rb') as content:
                upload_file(workflow_id, content, _f['new_path'], token)
                successful.append('{} saved as {}'.format(
                    _f['path'], _f['new_path']))
        except (IOError, FileUploadError):
            errors.append(_f['path'])

    return jsonify({
        'workflow_id': workflow_id,
        'successful': successful,
        'errors': errors
    }), 200


@workflows_bp.route('/reana/<workflow_id>/files/<path:path>',
                    methods=['DELETE'])
@login_required
@pass_workflow(with_access=True)
def delete_reana_workflow_files(workflow_id, path=None, workflow=None):
    """Delete files from a workflow."""
    rec_uuid = resolve_uuid(workflow_id)
    token = get_reana_token(rec_uuid)

    try:
        resp = delete_file(workflow_id, path, token)
        return jsonify(resp)
    except FileDeletionError:
        return jsonify({
            'message':
            '{} did not match any existing file. '
            'Aborting deletion.'.format(path)
        }), 400
