#!/usr/bin/env python3
"""MALTS 2.0.0 Task, state and recovery CLI. Select a verified runtime and workspace."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True

import argparse
import json
import sqlite3
import inspect
from contextlib import closing
from pathlib import Path
from v2_state_store import StateStore, StateConflict, SCHEMA_VERSION
from v2_operations import Operations, MAX_INLINE_PARAMETERS_BYTES
from v2_evidence import BlobStore, _regular_path
from v2_acceptance import Acceptance
from v2_backup import backup, verify_backup, restore_backup
from v2_recovery import Recovery, digest
from v2_runs import Runs
from v2_local_host import LocalFileHost
from v2_growth import Growth
from v2_governance import Governance
from v2_legacy_reader import inspect_workspace,annotate_archive_only,inspect_legacy_activity
from v2_migration import stage_controls,verify_capsule,inventory_hash,import_definitions,verify_definition_import,finalize_definition_import,retry_definition_import,legacy_control_context,legacy_artifact_context,legacy_session_run_context,MigrationReview
from v2_adoption import Adoption,require_active_binding
from v2_forward_recovery import ForwardRecovery,UnavailableStoreRecovery
from v2_service import ACTIONS,checked_arguments,load_request_json,action_contracts,execute_request,safe_error
from v2_compatibility import CLI_INTERFACE_VERSION,current_contract,inspect_contract

class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse messages can contain arbitrary supplied paths or tokens.
        self.exit(2, json.dumps({'decision':'ERROR','error_code':'CLI_ARGUMENTS',
                                'message':'Invalid command arguments; consult --help.'})+'\n')


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('capabilities')
    handoff=sub.add_parser('handoff-preview')
    handoff.add_argument('--state-dir',type=Path,required=True)
    handoff.add_argument('--task-id',required=True)
    handoff.add_argument('--task-revision',type=int,required=True)
    handoff.add_argument('--limit',type=int,default=20)
    handoff.add_argument('--language',choices=('en','zh-CN'),default='en')
    handoff.add_argument('--expected-source-token')
    handoff.add_argument('--note-id',action='append',default=[])
    handoff_note=sub.add_parser('handoff-note')
    handoff_note.add_argument('--state-dir',type=Path,required=True)
    handoff_note.add_argument('--project-id',required=True)
    handoff_note.add_argument('--note-id',required=True)
    blob_refs=sub.add_parser('blob-references')
    blob_refs.add_argument('--state-dir',type=Path,required=True)
    blob_refs.add_argument('--after-sequence',type=int,default=0)
    blob_refs.add_argument('--limit',type=int,default=64)
    blob_inventory=sub.add_parser('blob-inventory')
    blob_inventory.add_argument('--state-dir',type=Path,required=True)
    blob_inventory.add_argument('--prefix')
    blob_inventory.add_argument('--entry-budget',type=int,default=1000)
    blob_check=sub.add_parser('blob-inspect')
    blob_check.add_argument('--state-dir',type=Path,required=True)
    blob_check.add_argument('--digest',action='append',required=True)
    blob_check.add_argument('--reference-budget',type=int,default=1000)
    blob_check.add_argument('--max-bytes',type=int,default=1024*1024)
    artifact_check=sub.add_parser('artifact-check-definition')
    artifact_check.add_argument('--definition-file',type=Path,required=True)
    artifact_query=sub.add_parser('artifacts')
    artifact_query.add_argument('--state-dir',type=Path,required=True)
    artifact_query.add_argument('--project-id',required=True)
    artifact_query.add_argument('--after-artifact-id',default='')
    artifact_query.add_argument('--limit',type=int,default=20)
    maintenance=sub.add_parser('artifact-maintain')
    maintenance.add_argument('--state-dir',type=Path,required=True)
    maintenance.add_argument('--project-id',required=True)
    maintenance.add_argument('--as-of',required=True)
    maintenance.add_argument('--after-artifact-id',default='')
    maintenance.add_argument('--limit',type=int,default=20)
    maintenance.add_argument('--relation-budget',type=int,default=0)
    maintenance.add_argument('--declared-root',action='append',default=[])
    artifact_recovery=sub.add_parser('artifact-recovery-context')
    artifact_recovery.add_argument('--state-dir',type=Path,required=True)
    artifact_recovery.add_argument('--run-id',required=True)
    artifact_recovery.add_argument('--checkpoint-id',required=True)
    artifact_recovery.add_argument('--artifact-ref',action='append',default=[])
    artifact_recovery.add_argument('--max-artifacts',type=int,default=100)
    recovery_binding=sub.add_parser('artifact-recovery-binding')
    recovery_binding.add_argument('--state-dir',type=Path,required=True)
    recovery_binding.add_argument('--run-id',required=True)
    recovery_binding.add_argument('--checkpoint-id',required=True)
    recovery_handoff=sub.add_parser('artifact-recovery-handoff')
    recovery_handoff.add_argument('--state-dir',type=Path,required=True)
    recovery_handoff.add_argument('--task-id',required=True)
    recovery_handoff.add_argument('--task-revision',type=int,required=True)
    artifact_audit=sub.add_parser('artifact-audit-relations')
    artifact_audit.add_argument('--state-dir',type=Path,required=True)
    artifact_audit.add_argument('--project-id',required=True)
    artifact_audit.add_argument('--max-artifacts',type=int,default=100)
    artifact_audit.add_argument('--root-artifact-id')
    artifact_index=sub.add_parser('artifact-index-status')
    artifact_index.add_argument('--state-dir',type=Path,required=True)
    artifact_index.add_argument('--project-id',required=True)
    artifact_index.add_argument('--max-artifacts',type=int,default=1000)
    shared_verify=sub.add_parser('artifact-verify-shared')
    shared_verify.add_argument('--state-dir',type=Path,required=True)
    shared_verify.add_argument('--project-id',required=True)
    shared_verify.add_argument('--shared-id',required=True)
    shared_verify.add_argument('--relation-audit-budget',type=int,default=100)
    repair_plan=sub.add_parser('update-repair-plan')
    repair_plan.add_argument('--state-dir',type=Path,required=True)
    repair_plan.add_argument('--request-file',type=Path,required=True)
    mcp_config=sub.add_parser('mcp-config')
    mcp_config.add_argument('--host',choices=['codex','claude','opencode','deepseek-harness'],required=True)
    mcp_config.add_argument('--state-dir',type=Path,required=True)
    mcp_config.add_argument('--resource-root',type=Path,required=True)
    mcp_config.add_argument('--project-id',required=True)
    mcp_config.add_argument('--server-name',default='malts-v2')
    mcp_config.add_argument('--python-executable',type=Path)
    mcp_config.add_argument('--tool-root',type=Path)
    mcp_config.add_argument('--actor'); mcp_config.add_argument('--authority-ref')
    mcp_config.add_argument('--enable-write',action='store_true')
    mcp_config.add_argument('--allow-protected-input-capture',action='store_true')
    mcp_config.add_argument('--task-id');mcp_config.add_argument('--task-revision',type=int);mcp_config.add_argument('--dispatch-id')
    mcp_config.add_argument('--workflow-topic',choices=['phase','artifact','recovery'])
    adopted=sub.add_parser('workspace')
    adopted.add_argument('--workspace',type=Path,required=True)
    entry=sub.add_parser('entry-status')
    entry.add_argument('--workspace',type=Path,required=True);entry.add_argument('--tool-root',type=Path,required=True)
    entry.add_argument('--verify-package',action='store_true')
    entry.add_argument('--refresh-generation',type=Path)
    runtime_contract=sub.add_parser('runtime-contract');runtime_contract.add_argument('--root',type=Path,required=True)
    retirement=sub.add_parser('retirement-references')
    retirement.add_argument('--generation-root',type=Path,required=True);retirement.add_argument('--generation-id',required=True)
    retirement.add_argument('--reference-file',type=Path,action='append',default=[])
    retirement.add_argument('--host-journal',type=Path,action='append',default=[])
    retirement.add_argument('--state-dir',type=Path,action='append',default=[])
    retirement.add_argument('--expected-report-sha256')
    adoption_plan=sub.add_parser('legacy-adoption-plan')
    adoption_plan.add_argument('--state-dir',type=Path,required=True)
    adoption_plan.add_argument('--source-root',type=Path,required=True)
    adoption_plan.add_argument('--semantic-review-id',required=True)
    adoption_plan.add_argument('--adoption-id',required=True)
    adoption_plan.add_argument('--authority-ref',required=True)
    adoption_status=sub.add_parser('adoption-status')
    adoption_status.add_argument('--state-dir',type=Path,required=True)
    adoption_status.add_argument('--adoption-id',required=True)
    for command in ('legacy-forward-plan','forward-status'):
        forward=sub.add_parser(command)
        forward.add_argument('--state-dir',type=Path,required=True)
        forward.add_argument('--old-state-dir',type=Path,required=command=='legacy-forward-plan')
        forward.add_argument('--adoption-id',required=True)
        if command=='legacy-forward-plan':
            forward.add_argument('--backup-root',type=Path,required=True)
            forward.add_argument('--authority-ref',required=True)
    disaster=sub.add_parser('disaster-forward-plan')
    disaster.add_argument('--state-dir',type=Path,required=True)
    disaster.add_argument('--old-state-dir',type=Path,required=True)
    disaster.add_argument('--backup-root',type=Path,required=True)
    disaster.add_argument('--adoption-id',required=True)
    disaster.add_argument('--authority-ref',required=True)
    disaster.add_argument('--gap-review',type=Path,required=True)
    disaster_status=sub.add_parser('disaster-forward-status')
    disaster_status.add_argument('--state-dir',type=Path,required=True)
    disaster_status.add_argument('--adoption-id',required=True)
    init = sub.add_parser('init')
    init.add_argument('--state-dir', type=Path, required=True)
    init.add_argument('--project-id', required=True)
    init.add_argument('--goal', required=True)
    init.add_argument('--resource-root', type=Path)
    init.add_argument('--apply', action='store_true')
    change = sub.add_parser('request')
    change.add_argument('--state-dir', type=Path, required=True)
    change.add_argument('--request-file', type=Path, required=True)
    change.add_argument('--apply', action='store_true')
    change.add_argument('--tool-root',type=Path)
    show = sub.add_parser('task')
    show.add_argument('--state-dir', type=Path, required=True)
    show.add_argument('--task-id', required=True)
    context = sub.add_parser('context')
    context.add_argument('--state-dir', type=Path, required=True)
    context.add_argument('--task-id', required=True)
    context.add_argument('--limit', type=int, default=20)
    context.add_argument('--cursor-file', type=Path)
    growth = sub.add_parser('growth-query')
    growth.add_argument('--state-dir',type=Path,required=True)
    growth.add_argument('--owner',required=True)
    growth.add_argument('--task-type')
    growth.add_argument('--tool')
    growth.add_argument('--failure-signature')
    growth.add_argument('--after-id',default='')
    growth.add_argument('--limit',type=int,default=20)
    growth.add_argument('--max-bytes',type=int,default=262144)
    assessment = sub.add_parser('growth-assess')
    assessment.add_argument('--state-dir',type=Path,required=True)
    assessment.add_argument('--owner',required=True)
    assessment.add_argument('--candidate-id',required=True)
    task_check=sub.add_parser('task-verify')
    task_check.add_argument('--state-dir',type=Path,required=True)
    task_check.add_argument('--task-id',required=True)
    phase_check=sub.add_parser('phase-verify')
    phase_check.add_argument('--state-dir',type=Path,required=True)
    phase_check.add_argument('--completion-id',required=True)
    project_check=sub.add_parser('project-verify')
    project_check.add_argument('--state-dir',type=Path,required=True)
    project_check.add_argument('--completion-id',required=True)
    governance_context=sub.add_parser('governance-context')
    governance_context.add_argument('--state-dir',type=Path,required=True)
    governance_context.add_argument('--project-id',required=True)
    governance_context.add_argument('--after-phase-id',default='')
    governance_context.add_argument('--limit',type=int,default=20)
    budget=sub.add_parser('budget-status')
    budget.add_argument('--state-dir',type=Path,required=True)
    budget.add_argument('--project-id',required=True)
    budget.add_argument('--task-id')
    task_queue=sub.add_parser('task-queue')
    task_queue.add_argument('--state-dir',type=Path,required=True)
    task_queue.add_argument('--project-id',required=True)
    task_queue.add_argument('--after-task-id',default='')
    task_queue.add_argument('--limit',type=int,default=20)
    legacy=sub.add_parser('legacy-inspect')
    legacy.add_argument('--workspace',type=Path,required=True)
    legacy.add_argument('--max-controls',type=int,default=500)
    legacy.add_argument('--growth-ledger',action='append',default=[])
    legacy.add_argument('--payload-file',action='append',default=[])
    activity=sub.add_parser('legacy-activity')
    activity.add_argument('--workspace',type=Path,required=True)
    activity.add_argument('--max-files',type=int,default=2000)
    activity.add_argument('--max-bytes',type=int,default=67108864)
    stage=sub.add_parser('legacy-stage')
    stage.add_argument('--workspace',type=Path,required=True)
    stage.add_argument('--destination',type=Path,required=True)
    stage.add_argument('--expected-inventory-sha256')
    stage.add_argument('--archive-only-file',type=Path)
    stage.add_argument('--growth-ledger',action='append',default=[])
    stage.add_argument('--payload-file',action='append',default=[])
    stage.add_argument('--apply',action='store_true')
    capsule=sub.add_parser('legacy-verify-capsule')
    capsule.add_argument('--capsule',type=Path,required=True)
    capsule.add_argument('--expected-inventory-sha256')
    definition_import=sub.add_parser('legacy-import-definitions')
    definition_import.add_argument('--capsule',type=Path,required=True)
    definition_import.add_argument('--destination',type=Path,required=True)
    definition_import.add_argument('--mapping-file',type=Path,required=True)
    definition_import.add_argument('--expected-inventory-sha256',required=True)
    definition_import.add_argument('--expected-mapping-sha256')
    definition_import.add_argument('--apply',action='store_true')
    definition_verify=sub.add_parser('legacy-verify-import')
    definition_verify.add_argument('--state-dir',type=Path,required=True)
    definition_verify.add_argument('--expected-inventory-sha256',required=True)
    definition_verify.add_argument('--expected-mapping-sha256',required=True)
    finalize=sub.add_parser('legacy-finalize-import')
    finalize.add_argument('--state-dir',type=Path,required=True)
    finalize.add_argument('--expected-inventory-sha256',required=True)
    finalize.add_argument('--expected-mapping-sha256',required=True)
    finalize.add_argument('--apply',action='store_true')
    retry=sub.add_parser('legacy-retry-import')
    retry.add_argument('--capsule',type=Path,required=True)
    retry.add_argument('--failed-target',type=Path,required=True)
    retry.add_argument('--destination',type=Path,required=True)
    retry.add_argument('--mapping-file',type=Path,required=True)
    retry.add_argument('--expected-inventory-sha256',required=True)
    retry.add_argument('--expected-mapping-sha256',required=True)
    retry.add_argument('--writer-stopped-ref',required=True)
    retry.add_argument('--expected-failed-sha256')
    retry.add_argument('--apply',action='store_true')
    semantic=sub.add_parser('legacy-review-semantics')
    semantic.add_argument('--state-dir',type=Path,required=True)
    semantic.add_argument('--report-file',type=Path,required=True)
    semantic.add_argument('--expected-inventory-sha256',required=True)
    semantic.add_argument('--expected-mapping-sha256',required=True)
    semantic.add_argument('--expected-plan-sha256')
    semantic.add_argument('--apply',action='store_true')
    historical=sub.add_parser('legacy-context')
    historical.add_argument('--state-dir',type=Path,required=True)
    historical.add_argument('--project-id',required=True)
    historical.add_argument('--role',choices=['PROJECT','PHASE','SESSION','PLAN','RESULT_CONTRACT','RESULT_EVENT','RESULT_PROJECTION','RESULT_CONTRACT_HISTORY','RESULT_EVENT_HISTORY','PHASE_BOUNDARY','ARTIFACT_SHARED_INDEX','ARTIFACT_ARCHIVE_INDEX','GROWTH_LEDGER','GROWTH_SIGNAL','GROWTH_CANDIDATE'],required=True)
    historical.add_argument('--source-id',required=True)
    historical.add_argument('--section')
    historical.add_argument('--json-field')
    historical.add_argument('--max-characters',type=int,default=4096)
    historical_run=sub.add_parser('legacy-run-context')
    historical_run.add_argument('--state-dir',type=Path,required=True)
    historical_run.add_argument('--project-id',required=True)
    historical_run.add_argument('--run-id',required=True)
    historical_run.add_argument('--max-characters',type=int,default=4096)
    artifacts=sub.add_parser('legacy-artifacts')
    artifacts.add_argument('--state-dir',type=Path,required=True)
    artifacts.add_argument('--project-id',required=True)
    artifacts.add_argument('--source-role',choices=['PHASE','SESSION','ARTIFACT_SHARED_INDEX','ARTIFACT_ARCHIVE_INDEX'],required=True)
    artifacts.add_argument('--source-id',required=True)
    artifacts.add_argument('--after-row',type=int,default=0)
    artifacts.add_argument('--limit',type=int,default=20)
    artifacts.add_argument('--max-bytes',type=int,default=16384)
    save = sub.add_parser('backup')
    save.add_argument('--state-dir', type=Path, required=True)
    save.add_argument('--destination', type=Path, required=True)
    save.add_argument('--apply', action='store_true')
    check = sub.add_parser('verify-backup')
    check.add_argument('--destination', type=Path, required=True)
    restore = sub.add_parser('restore')
    restore.add_argument('--backup-root', type=Path, required=True)
    restore.add_argument('--destination', type=Path, required=True)
    restore.add_argument('--expected-backup-sha256')
    restore.add_argument('--apply', action='store_true')
    recovery_inspect = sub.add_parser('recovery-inspect')
    recovery_inspect.add_argument('--state-dir', type=Path, required=True)
    recovery_review = sub.add_parser('recovery-review')
    recovery_review.add_argument('--state-dir', type=Path, required=True)
    recovery_review.add_argument('--review-file', type=Path, required=True)
    recovery_review.add_argument('--expected-plan-sha256')
    recovery_review.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        request = None
        if args.command == 'request':
            request = load_request_json(args.request_file)
            checked_arguments(request)
        if args.command == 'handoff-preview':
            from v2_handoff import preview_handoff
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=preview_handoff(store,task_id=args.task_id,task_revision=args.task_revision,
                    limit=args.limit,language=args.language,expected_source_token=args.expected_source_token,note_ids=args.note_id)
        elif args.command == 'handoff-note':
            from v2_handoff import HandoffNotes
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=HandoffNotes(store).read(project_id=args.project_id,note_id=args.note_id)
        elif args.command == 'artifact-check-definition':
            from v2_contracts import artifact_definition
            _regular_path(args.definition_file)
            with args.definition_file.open('rb') as stream:
                raw=stream.read(32769)
            if len(raw)>32768:raise ValueError('Artifact definition exceeds its byte budget')
            def artifact_pairs(items):
                result={}
                for key,value in items:
                    if key in result:raise ValueError('Duplicate Artifact definition field')
                    result[key]=value
                return result
            artifact_definition(json.loads(raw.decode('utf-8'),object_pairs_hook=artifact_pairs))
            result={'decision':'DEFINITION_SHAPE_VALID','writes_performed':False,'enrolled':False,
                    'payload_read':False,'authority_granted':False,'owner_and_targets_verified':False,
                    'physical_locator_verified':False,'verification_result':'NOT_RUN'}
        elif args.command == 'artifact-verify-shared':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).verify_shared(project_id=args.project_id,shared_id=args.shared_id,relation_audit_budget=args.relation_audit_budget)
        elif args.command == 'artifact-audit-relations':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).audit_relations(project_id=args.project_id,max_artifacts=args.max_artifacts,root_artifact_id=args.root_artifact_id)
        elif args.command == 'artifact-recovery-handoff':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                store.connection.execute('BEGIN')
                result=Artifacts(store).recovery_handoff(task_id=args.task_id,task_revision=args.task_revision)
                store.connection.execute('ROLLBACK')
        elif args.command == 'artifact-recovery-binding':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).verify_recovery_binding(run_id=args.run_id,checkpoint_id=args.checkpoint_id)
        elif args.command == 'artifact-recovery-context':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).recovery_context(run_id=args.run_id,checkpoint_id=args.checkpoint_id,
                    artifact_refs=args.artifact_ref,max_artifacts=args.max_artifacts)
        elif args.command == 'blob-references':
            from v2_evidence import blob_references
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=blob_references(store,after_sequence=args.after_sequence,limit=args.limit)
        elif args.command == 'blob-inventory':
            from v2_evidence import inventory_blobs
            with closing(StateStore(args.state_dir/'state.db',readonly=True)):
                result=inventory_blobs(BlobStore(args.state_dir/'blobs',readonly=True),
                    prefix=args.prefix,entry_budget=args.entry_budget)
        elif args.command == 'blob-inspect':
            from v2_evidence import inspect_blobs
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=inspect_blobs(store,BlobStore(args.state_dir/'blobs',readonly=True),
                    digests=args.digest,reference_budget=args.reference_budget,max_bytes=args.max_bytes)
        elif args.command == 'artifact-maintain':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).maintenance(project_id=args.project_id,as_of=args.as_of,
                    after_artifact_id=args.after_artifact_id,limit=args.limit,relation_budget=args.relation_budget,
                    declared_roots=args.declared_root)
        elif args.command == 'artifacts':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).context(project_id=args.project_id,after_artifact_id=args.after_artifact_id,limit=args.limit)
        elif args.command == 'artifact-index-status':
            from v2_artifacts import Artifacts
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Artifacts(store).relation_index_status(project_id=args.project_id,max_artifacts=args.max_artifacts)
        elif args.command == 'capabilities':
            actions=action_contracts()
            from v2_legacy_reader import source_profiles
            from v2_runtime_mutex import capabilities as runtime_mutex_capabilities
            result={'interface':'malts.candidate.cli','interface_version':CLI_INTERFACE_VERSION,'database_schema':SCHEMA_VERSION,
                    'runtime_format_contract':current_contract(),
                    'runtime_exclusion_primitive':runtime_mutex_capabilities(),
                    'legacy_reader_profiles':source_profiles(),
                    'entry_negotiation':{'command':'entry-status','read_only':True,'active_identity_retries':1,
                        'optional_update_lookup':True,'explicit_candidate_required':True,'remote_update_lookup':False,'runtime_write_fence':False},
                    'context_presentation_version':2,
                    'mcp_worker_binding':{'optional_task_revision_dispatch_scope':True,'transaction_recheck':True,'os_authentication':False},
                    'task_verification':{'state':'VERIFYING','managed_effects_frozen':True,
                        'rework_invalidates_prior_evidence':True,'physical_external_writer_fence':False},
                    'task_effect_recovery':{'state':'RECOVERY_REQUIRED','scope':'REGISTERED_OPERATION_EFFECTS',
                                            'cancellation_preserved':True,'host_quiescence_implied':False},
                    'host_execution':{'controller_python_api':'v2_host_execution','builtin_agent_adapter':False,
                                      'actual_agent_qualification':False,'nested_delegation_qualified':False,
                                      'budget_scope':'PROJECT_MANAGED_ADAPTERS','whole_host_occupancy_known':False},
                    'windows_process_boundary':{'controller_primitive':'v2_windows_job.WindowsJob',
                                                'scope':'ASSOCIATED_WINDOWS_JOB_PROCESSES',
                                                'persistent_supervisor':False,'real_time_deadline_guaranteed':False},
                    'local_process_host':{'controller_adapter':'v2_process_host.SupervisedProcessHost',
                                          'durable_journal':True,'independent_bounded_supervisor':True,
                                          'agent_stdio_transport':False,'actual_agent_qualification':False,
                                          'candidate_transport_scope':'CODEX_SYNTHETIC_PROTOCOL_ONLY',
                                          'real_time_deadline_guaranteed':False,'bounded_generic_stdio':True,
                                          'event_profiles':['bounded-jsonl-v1','codex-jsonl-v1'],'raw_output_retained':False,
                                          'journal_version':3,'private_native_result':True,
                                          'unavailable_journal_reconciliation':True,'missing_journal_auto_relaunch':False,
                                          'codex_profile_builder':'v2_codex_profile.CodexReadOnlyProfile',
                                          'codex_worker_profile_builder':'v2_codex_profile.CodexWorkerProfile',
                                          'worker_actor_bound_at_start':True,'native_worker_model_qualified':False,
                                          'effective_model_verified':False},
                    'dispatch_budget_recovery':{'controller_amendment':True,'restored_usage':'UNKNOWN_UNTIL_RECONCILED',
                                                'recovery_call_allowance_required':True,'independent_usage_verifier':False},
                    'max_new_inline_parameters_bytes':MAX_INLINE_PARAMETERS_BYTES,
                    'operation_inputs':{'default':'METADATA_ONLY','protected_capture_requires_authority':True,
                                        'protection_profile':'WINDOWS_DPAPI_CURRENT_USER','cross_machine_qualified':False},
                    'evidence_storage':{'body_format':'PROTECTED_EVIDENCE_V1','plaintext_fallback':False,
                                        'growth_byte_accounting':'STORED_EVIDENCE_BYTES',
                                        'mcp_raw_file_growth_allowed':False,
                                        'controller_derivation':'evidence.derive','source_permission':'derivation',
                                        'transitive_withdrawal_enforced_on_read':True,'automatic_sanitization':False},
                    'observation_references':{'format':'PROTECTED_OBSERVATION_REFERENCE_V1','max_utf8_bytes':16384,
                                              'plaintext_fallback':False,'client_read_endpoint':False},
                    'checkpoint_text':{'format':'PROTECTED_CHECKPOINT_TEXT_V1','native_and_imported_projection':True,
                                       'legacy_source_files_rewritten':False,'plaintext_fallback':False},
                    'definition_values':{'format':'PROTECTED_DEFINITION_VALUE_V1',
                                         'request_fingerprint':'HMAC_SHA256_PER_PROJECT_PROTECTED_KEY',
                                         'global_key_file':False,'preview_read_mode':'BOUNDED_PROTECTED_PROJECTION',
                                         'preview_characters':2048,'max_protected_preview_characters':32768,
                                         'preview_verifies_full_body':False,'controller_refresh':'definition.refresh-preview'},
                    'qualification':'UNQUALIFIED_MAINTENANCE_CANDIDATE','actions':actions,
                    'optional_mcp_bridge':{'entry':'v2_mcp.py','default_mode':'READ_ONLY','tested_sdk':'1.26.0',
                        'tested_protocol':'2025-11-25','runtime_dependency_checked':False,
                        'modern_protocol_qualified':False,'native_host_integration_qualified':False},
                    'host_authentication_enforced':False,'unmediated_host_actions_controlled':False,
                    'current_result_verifiers':['create-file','read-file','update-file'],
                    'local_update_profile':{'name':'WINDOWS_EXCLUSIVE_HANDLE','available':sys.platform=='win32','max_bytes':16777216,
                                            'partial_write_auto_repair':False,'preimage_in_backup':True,
                                            'reviewed_partial_repair':True,'repair_plan_command':'update-repair-plan'},
                    'automated_evidence_verifiers':{'verification.managed-files':{'method':'managed-file-integrity','level':'C','business_correctness_verified':False}},
                    'adoption':{'plan':True,'apply':'TRUSTED_IN_PROCESS_HOST_ONLY','binding_resolution':True,
                                'legacy_runtime_rollback_supported':False,'recovery_direction':'V2_ONLY',
                                'legacy_rollback_scene_recovery_qualified':False,
                                'native_host_adapters_qualified':False,'forward_reconciliation_implemented':True,
                                'forward_profile':'RECONCILED_CURRENT_BACKUP_WITH_READABLE_OLD_STORE'},
                    'migration_supported':False,'writes_performed':False,'execution_authorized':False}
        elif args.command=='update-repair-plan':
            from v2_update_repair import plan_update_repair
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=plan_update_repair(LocalFileHost(store),**load_request_json(args.request_file))
        elif args.command=='mcp-config':
            from v2_mcp import configuration_fragment
            result=configuration_fragment(host=args.host,state_dir=args.state_dir,resource_root=args.resource_root,
                project_id=args.project_id,server_name=args.server_name,python_executable=args.python_executable,
                actor=args.actor,authority_ref=args.authority_ref,enable_write=args.enable_write,allow_protected_input_capture=args.allow_protected_input_capture,
                task_id=args.task_id,task_revision=args.task_revision,dispatch_id=args.dispatch_id,tool_root=args.tool_root,
                workflow_topic=args.workflow_topic)
        elif args.command == 'runtime-contract':
            result=inspect_contract(args.root)
        elif args.command == 'retirement-references':
            from v2_retirement import inspect_references
            result=inspect_references(generation_root=args.generation_root,generation_id=args.generation_id,
                reference_files=args.reference_file,host_journals=args.host_journal,core_states=args.state_dir,expected_report_sha256=args.expected_report_sha256)
        elif args.command == 'entry-status':
            from v2_entry import inspect_entry
            result=inspect_entry(workspace=args.workspace,tool_root=args.tool_root,verify_package=args.verify_package,refresh_generation=args.refresh_generation)
        elif args.command == 'workspace':
            _regular_path(args.workspace/'runtime/v2_binding.json')
            if not (args.workspace/'runtime/v2_binding.json').exists():
                from v2_entry import inspect_native_workspace
                result=inspect_native_workspace(args.workspace)
            else:
                binding=load_request_json(args.workspace/'runtime/v2_binding.json')
                target=Path(binding['state_dir'])
                if not target.is_absolute() or str(target).startswith(('\\\\','//')): raise ValueError('Adopted store must be a local absolute path')
                if Path(binding['source_root']).resolve()!=args.workspace.resolve(): raise StateConflict('Workspace binding source differs')
                with closing(StateStore(target/'state.db',readonly=True)) as store:
                    require_active_binding(store)
                    result={'decision':'ADOPTED_WORKSPACE','state_dir':str(target),'epoch':binding['epoch'],
                            'binding_status':'VERIFIED','reconciliation_required':bool(store.connection.execute('SELECT reconciliation_required FROM recovery_state').fetchone()[0]),
                            'execution_authorized':False,'writes_performed':False}
        elif args.command in {'disaster-forward-plan','disaster-forward-status'}:
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                disaster=UnavailableStoreRecovery(store)
                if args.command=='disaster-forward-status': result=disaster.inspect(adoption_id=args.adoption_id)
                else: result=disaster.plan(backup_root=args.backup_root,old_state_dir=args.old_state_dir,
                    adoption_id=args.adoption_id,authority_ref=args.authority_ref,gap_review=load_request_json(args.gap_review))
        elif args.command == 'forward-status':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=ForwardRecovery(store).inspect(adoption_id=args.adoption_id)
                if args.old_state_dir is not None and args.old_state_dir.resolve()!=Path(result['plan']['old_state_dir']).resolve():
                    raise StateConflict('Forward status original store differs from the requested path')
        elif args.command == 'legacy-forward-plan':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store, closing(StateStore(args.old_state_dir/'state.db',readonly=True)) as old:
                forward=ForwardRecovery(store,old)
                result=forward.plan(backup_root=args.backup_root,adoption_id=args.adoption_id,authority_ref=args.authority_ref)
        elif args.command == 'adoption-status':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Adoption(store).inspect(adoption_id=args.adoption_id)
        elif args.command == 'legacy-adoption-plan':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=Adoption(store).plan(source_root=args.source_root,semantic_review_id=args.semantic_review_id,
                                           adoption_id=args.adoption_id,authority_ref=args.authority_ref)
        elif args.command == 'legacy-context':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=legacy_control_context(store,project_id=args.project_id,role=args.role,source_id=args.source_id,
                                               section=args.section,json_field=args.json_field,max_characters=args.max_characters)
        elif args.command == 'legacy-artifacts':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=legacy_artifact_context(store,project_id=args.project_id,source_role=args.source_role,
                    source_id=args.source_id,after_row=args.after_row,limit=args.limit,max_bytes=args.max_bytes)
        elif args.command == 'legacy-run-context':
            with closing(StateStore(args.state_dir/'state.db',readonly=True)) as store:
                result=legacy_session_run_context(store,project_id=args.project_id,run_id=args.run_id,max_characters=args.max_characters)
        elif args.command == 'legacy-verify-import':
            result=verify_definition_import(args.state_dir,expected_inventory_sha256=args.expected_inventory_sha256,expected_mapping_sha256=args.expected_mapping_sha256)
        elif args.command == 'legacy-review-semantics':
            report=load_request_json(args.report_file)
            with closing(StateStore(args.state_dir/'state.db',readonly=not args.apply)) as store:
                review=MigrationReview(store)
                parameters={'inventory_sha256':args.expected_inventory_sha256,'mapping_sha256':args.expected_mapping_sha256}
                if args.apply:
                    if not args.expected_plan_sha256: raise ValueError('Semantic review apply requires its preview hash')
                    result=review.apply(report,**parameters,expected_plan_sha256=args.expected_plan_sha256)
                else: result=review.plan(report,**parameters)
        elif args.command == 'legacy-finalize-import':
            result=finalize_definition_import(args.state_dir,expected_inventory_sha256=args.expected_inventory_sha256,
                                             expected_mapping_sha256=args.expected_mapping_sha256,apply=args.apply)
        elif args.command == 'legacy-retry-import':
            result=retry_definition_import(args.capsule,args.failed_target,args.destination,
                expected_inventory_sha256=args.expected_inventory_sha256,mapping=load_request_json(args.mapping_file),
                expected_mapping_sha256=args.expected_mapping_sha256,writer_stopped_ref=args.writer_stopped_ref,
                expected_failed_sha256=args.expected_failed_sha256,apply=args.apply)
        elif args.command == 'legacy-import-definitions':
            mapping=load_request_json(args.mapping_file)
            verify_capsule(args.capsule,expected_inventory_sha256=args.expected_inventory_sha256)
            if args.apply:
                if not args.expected_mapping_sha256: raise ValueError('Definition import requires reviewed mapping hash')
                result=import_definitions(args.capsule,args.destination,expected_inventory_sha256=args.expected_inventory_sha256,
                                          mapping=mapping,expected_mapping_sha256=args.expected_mapping_sha256)
            else:
                result={'decision':'DEFINITION_IMPORT_PREVIEW','inventory_sha256':args.expected_inventory_sha256,
                        'mapping_sha256':inventory_hash(mapping),'readiness':'NOT_EVALUATED','writes_performed':False,
                        'migration_complete':False,'execution_authorized':False}
        elif args.command == 'legacy-verify-capsule':
            result=verify_capsule(args.capsule,expected_inventory_sha256=args.expected_inventory_sha256)
        elif args.command == 'legacy-stage':
            inventory=inspect_workspace(args.workspace,growth_ledgers=args.growth_ledger,payload_files=args.payload_file)
            if args.archive_only_file:
                inventory=annotate_archive_only(inventory,load_request_json(args.archive_only_file))
            if args.apply:
                if not args.expected_inventory_sha256: raise ValueError('Staging requires reviewed inventory hash')
                result=stage_controls(args.workspace,args.destination,inventory=inventory,expected_inventory_sha256=args.expected_inventory_sha256)
            else:
                result={'decision':'SOURCE_STAGE_PREVIEW','inventory_sha256':inventory_hash(inventory),
                        'archive_only_count':sum('archive_only' in r for r in inventory['records']),
                        'issues':inventory['issues'],'unverified_identity_count':sum(r['identity_verification']!='MATCH' for r in inventory['records']),
                        'source_record_count':len(inventory['records']),'writes_performed':False,
                        'semantic_import_performed':False,'destination_readiness':'NOT_EVALUATED'}
        elif args.command == 'legacy-inspect':
            result=inspect_workspace(args.workspace,max_controls=args.max_controls,growth_ledgers=args.growth_ledger,payload_files=args.payload_file)
        elif args.command == 'legacy-activity':
            result=inspect_legacy_activity(args.workspace,max_files=args.max_files,max_bytes=args.max_bytes)
        elif args.command == 'restore':
            if args.apply:
                if not args.expected_backup_sha256:
                    raise ValueError('Restore apply requires --expected-backup-sha256 from its preview')
                result = restore_backup(args.backup_root, args.destination, expected_manifest_sha256=args.expected_backup_sha256)
                result['decision'] = 'RESTORED_QUARANTINED'
            else:
                manifest = verify_backup(args.backup_root)
                result = {'decision': 'RESTORE_PREVIEW', 'backup_sha256': digest(manifest),
                          'backup_root': str(args.backup_root), 'destination': str(args.destination),
                          'writes_performed': False, 'execution_authorized': False}
        elif args.command in {'recovery-inspect', 'recovery-review'}:
            applying = args.command == 'recovery-review' and args.apply
            with closing(StateStore(args.state_dir/'state.db', readonly=not applying)) as store:
                recovery = Recovery(store)
                if args.command == 'recovery-inspect':
                    result = recovery.inspect()
                else:
                    report = load_request_json(args.review_file)
                    if applying:
                        if not args.expected_plan_sha256:
                            raise ValueError('Recovery apply requires --expected-plan-sha256 from its preview')
                        result = recovery.apply(report, expected_plan_sha256=args.expected_plan_sha256)
                    else:
                        result = recovery.plan(report)
        elif args.command in {'init', 'request', 'backup'} and not args.apply:
            # Preview declares intent only; it is not a validation or permission receipt.
            result = {'decision': 'NOT_APPLIED', 'writes_performed': False, 'readiness': 'NOT_EVALUATED',
                      'command': args.command, 'state_dir': str(args.state_dir)}
            if request is not None:
                result['action'] = request['action']
                result['argument_names'] = sorted(request['arguments'])
        elif args.command == 'init':
            _regular_path(args.state_dir.absolute())
            args.state_dir.mkdir()
            with closing(StateStore.initialize(args.state_dir/'state.db', args.project_id, args.goal, resource_root=args.resource_root)):
                (args.state_dir/'blobs').mkdir()
            result = {'decision': 'INITIALIZED', 'project_id': args.project_id, 'state_dir': str(args.state_dir)}
        elif args.command == 'verify-backup':
            result = {'decision': 'VERIFIED_BACKUP', 'manifest': verify_backup(args.destination),
                      'verification_scope':'STORED_BYTES_AND_REFERENCES','plaintext_recovery_verified':False}
        elif args.command=='request' and args.tool_root is not None:
            from v2_runtime_admission import execute_admitted_request
            result=execute_admitted_request(tool_root=args.tool_root,state_dir=args.state_dir,request=request)
        else:
            with closing(StateStore(args.state_dir/'state.db', readonly=args.command in {'task','task-verify', 'backup', 'context','growth-query','growth-assess','phase-verify','project-verify','governance-context','budget-status','task-queue'})) as store:
                if args.command == 'task-verify':
                    result=Acceptance(store,BlobStore(args.state_dir/'blobs',readonly=True)).verify_task_completion(task_id=args.task_id)
                elif args.command == 'task-queue':
                    result=Governance(store).task_queue(project_id=args.project_id,after_task_id=args.after_task_id,limit=args.limit)
                elif args.command == 'budget-status':
                    result=Operations(store).budget_status(project_id=args.project_id,task_id=args.task_id)
                elif args.command == 'governance-context':
                    result=Governance(store).context(project_id=args.project_id,after_phase_id=args.after_phase_id,limit=args.limit)
                elif args.command == 'project-verify':
                    result=Governance(store).verify_project_completion(completion_id=args.completion_id)
                elif args.command == 'phase-verify':
                    result=Governance(store).verify_phase_completion(completion_id=args.completion_id)
                elif args.command == 'growth-assess':
                    result=Growth(store,BlobStore(args.state_dir/'blobs',readonly=True)).assess(candidate_id=args.candidate_id,owner=args.owner)
                elif args.command == 'growth-query':
                    result=Growth(store,BlobStore(args.state_dir/'blobs',readonly=True)).retrieve(
                        owner=args.owner,task_type=args.task_type,tool=args.tool,
                        failure_signature=args.failure_signature,after_id=args.after_id,limit=args.limit,max_bytes=args.max_bytes)
                elif args.command == 'context':
                    cursor = load_request_json(args.cursor_file) if args.cursor_file else None
                    result = store.current_context(args.task_id, limit=args.limit, cursor=cursor)
                elif args.command == 'task':
                    result = {'decision': 'FOUND', 'task': store.task(args.task_id)}
                    if result['task'] is None:
                        raise ValueError('Task not found')
                elif args.command == 'backup':
                    result = {'decision': 'BACKUP_CREATED', 'manifest': backup(store, BlobStore(args.state_dir/'blobs', readonly=True), args.destination)}
                else:
                    result=execute_request(store,request)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        print(json.dumps(safe_error(error),ensure_ascii=False),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
