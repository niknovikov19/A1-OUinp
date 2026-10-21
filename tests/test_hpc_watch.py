from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import hpc_watch as watch


RUN_ID = 'watch-fixture-001'
COMMIT = 'a' * 40


class FakeClock:
    def __init__(self):
        """Keep wall and monotonic time separate for clock-jump tests. """
        self.wall = 1792454400
        self.mono = 0
        self.sleeps = []

    def time(self):
        """Read simulated wall time. """
        return self.wall

    def monotonic(self):
        """Read simulated elapsed time. """
        return self.mono

    def sleep(self, seconds):
        """Advance time without slowing the test suite. """
        self.sleeps.append(seconds)
        self.wall += seconds
        self.mono += seconds


def scheduler(job_id, state='RUNNING', exit_code=None):
    """Construct the same bounded scheduler fields as the installed helper. """
    return {
        'job_id': job_id, 'source': 'sacct' if state in watch.SLURM_TERMINAL_STATES else 'squeue',
        'raw_state': state, 'normalized_state': state.lower(), 'reason': '',
        'exit_code': exit_code if exit_code is not None else ('0:0' if state == 'COMPLETED' else ''),
        'accounting_gap': False, 'retry_after_sec': None,
    }


def status(main='RUNNING', children=('RUNNING',), exit_codes=None):
    """Build a run-bound status with stable parameter and output identities. """
    child_records = []
    for index, state in enumerate(children):
        key = f'sim-{index:03d}'
        code = exit_codes[index] if exit_codes else None
        child_records.append({
            'child_key': key, 'slurm_job_id': 101 + index,
            'parameters': {'seed': index}, 'expected_outputs': [f'results/{key}.json'],
            'stdout_path': f'jobs/{key}.out', 'stderr_path': f'jobs/{key}.err',
            'scheduler': scheduler(101 + index, state, code),
        })
    return {
        'schema_version': 1, 'operation': 'job-status', 'status': 'ok', 'run_id': RUN_ID,
        'git_commit': COMMIT, 'slurm_job_id': 100, 'scheduler': scheduler(100, main),
        'children': child_records, 'observed_at_utc': watch.utc_string(1792454400),
    }


def reply(payload, code=0, error=None):
    """Build one helper subprocess result without invoking HPC. """
    return {'returncode': code, 'stdout': json.dumps(payload), 'stderr': '',
            'error': error, 'interrupted': False, 'local_error': False}


class FakeRunner:
    def __init__(self, responses, clock):
        """Return prescribed observations and retain exact helper operations. """
        self.responses = list(responses)
        self.clock = clock
        self.calls = []

    def __call__(self, run_id, operation, child_key, timeout):
        """Repeat the last status and supply bounded incremental log fixtures. """
        self.calls.append((self.clock.time(), operation, child_key, timeout))
        if operation == 'log':
            return reply({'operation': 'job-log', 'status': 'ok', 'run_id': run_id,
                          'slurm_job_id': 100 if child_key is None else 101 + int(child_key.split('-')[1]),
                          'child_key': child_key, 'streams': {'stdout': {'content': 'new log', 'more_available': False}}})
        result = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if callable(result):
            return result(timeout)
        result = deepcopy(result)
        try:
            payload = json.loads(result['stdout']) if result['stdout'] else None
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get('operation') == 'job-status':
            payload['observed_at_utc'] = watch.utc_string(self.clock.time())
            result['stdout'] = json.dumps(payload)
        return result


class WatcherTests(unittest.TestCase):
    def setUp(self):
        """Create a private local state directory and simulated time. """
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / 'watch'
        self.clock = FakeClock()
        self.addCleanup(self.tmp.cleanup)
        sync = patch.object(watch.os, 'fsync')
        sync.start()
        self.addCleanup(sync.stop)

    def run_watch(self, responses, resume=False, **options):
        """Run a complete foreground session with simulated helpers. """
        runner = FakeRunner(responses, self.clock)
        settings = watch.WatchOptions(**{'logs': False, **options})
        with watch.WatchStore(self.directory) as store:
            result = watch.Watcher(RUN_ID, store, settings, runner, self.clock).run(resume)
        return result, runner

    def test_unchanged_wait_collects_observations_without_returning_each_poll(self):
        """Keep routine HPC checks inside one watcher session until the checkpoint. """
        result, runner = self.run_watch([reply(status())], codex_check_sec=1800)
        self.assertEqual(result['reason'], 'checkpoint')
        self.assertGreater(len(runner.calls), 10)
        self.assertEqual(self.clock.monotonic(), 1800)
        self.assertEqual(self.clock.sleeps[:5], [60] * 5)
        self.assertIn(120, self.clock.sleeps)
        self.assertLess(len(watch.encode(result).encode()), watch.MAX_REPORT_BYTES)
        observations = (self.directory / 'observations-0001.jsonl').read_text().splitlines()
        self.assertEqual(len(observations), len(runner.calls))
        self.assertEqual(json.loads(observations[0])['payload']['run_id'], RUN_ID)

    def test_growing_index_and_grouped_normal_transitions(self):
        """Accept newly submitted simulations and group changes at handoff. """
        observations = [status(children=()), status(children=('RUNNING', 'PENDING')),
                        status('COMPLETED', ('COMPLETED', 'COMPLETED'))]
        result, _ = self.run_watch([reply(value) for value in observations])
        self.assertEqual(result['reason'], 'scheduler-terminal')
        self.assertEqual(result['child_state_counts'], {'COMPLETED': 2})
        self.assertEqual(result['observed_children'], 2)
        self.assertFalse(result['expected_child_coverage_verified'])
        self.assertFalse(result['output_files_verified'])

    def test_completed_main_with_no_children_does_not_certify_coverage(self):
        """Report scheduler termination while leaving planned work and files unverified. """
        result, _ = self.run_watch([reply(status('COMPLETED', ()))])
        self.assertEqual(result['reason'], 'scheduler-terminal')
        self.assertEqual(result['observed_children'], 0)
        self.assertFalse(result['expected_child_coverage_verified'])

    def test_main_ended_with_live_children_requires_attention(self):
        """Return the live-child condition instead of certifying a settled run. """
        result, _ = self.run_watch([reply(status('COMPLETED'))])
        self.assertEqual(result['reason'], 'attention')
        self.assertEqual(result['attention'][0]['state'], 'main-ended-with-active-simulations')

    def test_failed_states_and_nonzero_completed_exit_require_attention(self):
        """Inspect actual Slurm tokens and exit codes on the first observation. """
        for state, code in (('FAILED', '1:0'), ('CANCELLED', ''), ('TIMEOUT', ''),
                            ('OUT_OF_MEMORY', ''), ('COMPLETED', '1:0')):
            with self.subTest(state=state, code=code):
                self.directory = Path(self.tmp.name) / f'{state}-{code.replace(":", "-")}'
                result, _ = self.run_watch([reply(status(children=(state,), exit_codes=(code,)))])
                self.assertEqual(result['reason'], 'attention')

    def test_acknowledged_failure_does_not_create_a_tight_resume_loop(self):
        """Continue observing unchanged failed children after an attention handoff. """
        sample = reply(status(children=('FAILED', 'RUNNING')))
        result, _ = self.run_watch([sample], codex_check_sec=180)
        self.assertEqual(result['reason'], 'attention')
        result, runner = self.run_watch([sample], resume=True)
        self.assertEqual(result['reason'], 'checkpoint')
        self.assertGreater(len(runner.calls), 1)
        self.assertEqual(result['attention'], [])

    def test_new_failure_after_resume_requires_new_attention(self):
        """Do not suppress a second simulation's failure after acknowledging the first. """
        self.run_watch([reply(status(children=('FAILED', 'RUNNING')))])
        result, _ = self.run_watch([reply(status(children=('FAILED', 'FAILED')))], resume=True)
        self.assertEqual(result['reason'], 'attention')
        self.assertEqual(result['attention'][0]['key'], 'sim-001')

    def test_transport_recovery_and_persistent_failure_backoff(self):
        """Retry transient loss locally and stop after persistent unavailable status. """
        bad = reply({'operation': 'job-status', 'status': 'unknown'}, 3)
        result, runner = self.run_watch([bad, reply(status('COMPLETED', ('COMPLETED',)))])
        self.assertEqual(result['reason'], 'scheduler-terminal')
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(self.clock.sleeps, [60])
        self.directory = Path(self.tmp.name) / 'persistent'
        result, runner = self.run_watch([bad])
        self.assertEqual(result['reason'], 'monitoring-unavailable')
        self.assertEqual(len(runner.calls), 3)
        self.assertEqual(self.clock.sleeps[-2:], [60, 120])

    def test_unknown_accounting_and_unsupported_tokens_never_complete(self):
        """Keep successful-looking but unknown observations distinct from termination. """
        for change in ({'accounting_gap': True}, {'raw_state': 'UNRECOGNIZED'}, {'exit_code': ''}):
            with self.subTest(change=change):
                self.directory = Path(self.tmp.name) / str(len(list(Path(self.tmp.name).iterdir())))
                value = status('COMPLETED', ('COMPLETED',))
                value['children'][0]['scheduler'].update(change)
                result, _ = self.run_watch([reply(value)])
                self.assertEqual(result['reason'], 'monitoring-unavailable')
                self.assertEqual(result['uncertainty']['unknown_job_ids'], [101])

    def test_disappearing_child_remains_a_coverage_problem(self):
        """Do not forget a previously observed job when a later index is shorter. """
        first = reply(status(children=('RUNNING', 'RUNNING')))
        missing = reply(status('COMPLETED', ('COMPLETED',)))
        result, _ = self.run_watch([first, missing])
        self.assertEqual(result['reason'], 'monitoring-unavailable')
        self.assertEqual(result['previously_observed_children'], 2)
        self.assertEqual(result['uncertainty']['missing_children'], ['sim-001'])

    def test_changed_run_commit_child_parameters_or_paths_stop_immediately(self):
        """Reject identity changes before treating new data as progress. """
        for kind in ('run', 'commit', 'job', 'parameters', 'path'):
            with self.subTest(kind=kind):
                self.directory = Path(self.tmp.name) / kind
                changed = status()
                if kind == 'run':
                    changed['run_id'] = 'another-run'
                elif kind == 'commit':
                    changed['git_commit'] = 'b' * 40
                elif kind == 'job':
                    changed['children'][0]['slurm_job_id'] = 999
                    changed['children'][0]['scheduler']['job_id'] = 999
                elif kind == 'parameters':
                    changed['children'][0]['parameters'] = {'seed': 99}
                else:
                    changed['children'][0]['stdout_path'] = 'jobs/changed.out'
                result, runner = self.run_watch([reply(status()), reply(changed)])
                self.assertEqual(result['reason'], 'local-error')
                self.assertEqual(len(runner.calls), 2)

    def test_rejected_helper_and_malformed_json_do_not_retry(self):
        """Hand permanent problems back immediately instead of retrying them. """
        for sample, expected in ((reply({'status': 'rejected'}, 2), 'attention'),
                                 ({**reply({}), 'stdout': '{broken'}, 'local-error')):
            self.directory = Path(self.tmp.name) / expected
            result, runner = self.run_watch([sample])
            self.assertEqual(result['reason'], expected)
            self.assertEqual(len(runner.calls), 1)

    def test_pending_queue_reduces_poll_frequency(self):
        """Back off only after the complete observed tree stays pending. """
        result, _ = self.run_watch([reply(status('PENDING', ('PENDING',)))], codex_check_sec=1800)
        self.assertEqual(result['reason'], 'checkpoint')
        self.assertIn(300, self.clock.sleeps)

    def test_logs_are_periodic_bounded_and_diagnostic_only(self):
        """Read the main plus at most two affected children without draining all logs. """
        value = status(children=('FAILED', 'FAILED', 'FAILED', 'FAILED'))
        result, runner = self.run_watch([reply(value)], logs=True)
        self.assertEqual(result['reason'], 'attention')
        log_keys = [call[2] for call in runner.calls if call[1] == 'log']
        self.assertEqual(log_keys, [None, 'sim-000', 'sim-001'])
        self.directory = Path(self.tmp.name) / 'periodic'
        _, runner = self.run_watch([reply(status())], logs=True, codex_check_sec=660)
        self.assertEqual(sum(call[1] == 'log' for call in runner.calls), 2)

    def test_resume_preserves_interval_and_overall_deadline(self):
        """Stop at the original deadline rather than adding another full interval. """
        deadline = watch.utc_string(self.clock.time() + 250)
        result, _ = self.run_watch([reply(status())], until=deadline, codex_check_sec=120)
        self.assertEqual(result['reason'], 'checkpoint')
        result, _ = self.run_watch([reply(status())], resume=True)
        self.assertEqual(result['reason'], 'checkpoint')
        result, _ = self.run_watch([reply(status())], resume=True)
        self.assertEqual(result['reason'], 'deadline')
        result, runner = self.run_watch([reply(status())], resume=True)
        self.assertEqual(result['reason'], 'deadline')
        self.assertEqual(runner.calls, [])

    def test_deadline_extension_requires_an_explicit_option(self):
        """Reject accidental extensions while allowing a separately explicit extension. """
        deadline = watch.utc_string(self.clock.time() + 60)
        self.run_watch([reply(status())], until=deadline)
        later = watch.utc_string(self.clock.time() + 120)
        result, runner = self.run_watch([reply(status())], resume=True, until=later)
        self.assertEqual(result['reason'], 'local-error')
        self.assertEqual(runner.calls, [])
        result, _ = self.run_watch([reply(status())], resume=True, extend_until=later)
        self.assertEqual(result['reason'], 'deadline')

    def test_slow_helper_is_bounded_by_the_session(self):
        """Pass the remaining budget to the reader and return a checkpoint on expiry. """
        def timeout(seconds):
            """Use the complete available budget without real sleeping. """
            self.clock.sleep(seconds)
            return {**reply({}), 'returncode': -9, 'stdout': '', 'error': 'timeout'}

        result, runner = self.run_watch([timeout], codex_check_sec=20)
        self.assertEqual(result['reason'], 'checkpoint')
        self.assertEqual(runner.calls[0][3], 20)
        self.assertEqual(len(runner.calls), 1)

    def test_host_sleep_does_not_extend_the_deadline(self):
        """Notice a wall-clock jump even when monotonic time barely advanced. """
        def suspended(_timeout):
            """Simulate host suspension during a status read. """
            self.clock.wall += 1000
            return reply(status())

        result, runner = self.run_watch([suspended], codex_check_sec=120)
        self.assertEqual(result['reason'], 'checkpoint')
        self.assertEqual(len(runner.calls), 1)

    def test_interruption_saves_local_state_without_cancelling_hpc(self):
        """Return an interruption report and retain the last received status. """
        def interrupted(_timeout):
            """Interrupt an ordinary local sleep. """
            raise KeyboardInterrupt

        with patch.object(self.clock, 'sleep', side_effect=interrupted):
            result, runner = self.run_watch([reply(status())])
        self.assertEqual(result['reason'], 'interrupted')
        self.assertEqual([call[1] for call in runner.calls], ['status'])
        self.assertFalse(watch.watcher_status(self.directory)['watcher_running'])

    def test_second_watcher_cannot_overwrite_the_first(self):
        """Use a local file lock to prevent simultaneous ownership of one history. """
        with watch.WatchStore(self.directory):
            with self.assertRaises(BlockingIOError):
                with watch.WatchStore(self.directory):
                    self.fail('Second watcher acquired the lock')

    def test_corrupt_state_and_wrong_run_do_not_query_hpc(self):
        """Reject incompatible local histories before invoking the helper. """
        self.directory.mkdir()
        path = self.directory / 'state.json'
        path.write_text('{"schema_version": 1}')
        result, runner = self.run_watch([reply(status())], resume=True)
        self.assertEqual(result['reason'], 'local-error')
        self.assertEqual(runner.calls, [])
        self.assertEqual(json.loads(path.read_text()), {'schema_version': 1})

    def test_local_storage_limit_keeps_existing_observations(self):
        """Stop explicitly instead of deleting history or exceeding its budget. """
        runner = FakeRunner([reply(status())], self.clock)
        with watch.WatchStore(self.directory, storage_bytes=2200) as store:
            result = watch.Watcher(RUN_ID, store, watch.WatchOptions(logs=False), runner, self.clock).run()
            self.assertLessEqual(store.used, 2200)
        self.assertEqual(result['reason'], 'local-storage-limit')
        self.assertTrue((self.directory / 'observations-0001.jsonl').exists())

    def test_report_is_short_even_with_sixty_failed_children(self):
        """Bound the handoff while retaining omitted-attention counts. """
        result, _ = self.run_watch([reply(status(children=('FAILED',) * 60))])
        self.assertEqual(result['reason'], 'attention')
        self.assertEqual(len(result['attention']), 3)
        self.assertEqual(result['attention_omitted'], 57)
        self.assertLess(len(watch.encode(result).encode()), watch.MAX_REPORT_BYTES)

    def test_local_status_distinguishes_lock_and_observation_freshness(self):
        """Inspect the local watcher without issuing another HPC request. """
        runner = FakeRunner([reply(status())], self.clock)
        with watch.WatchStore(self.directory) as store:
            watcher = watch.Watcher(RUN_ID, store, runner=runner, clock=self.clock)
            watcher.initialize(False)
            local = watch.watcher_status(self.directory)
            self.assertTrue(local['watcher_running'])
            self.assertIsNone(local['last_good_at_utc'])
            self.assertFalse(local['status_checks_hpc'])
            self.assertEqual(runner.calls, [])
        self.assertFalse(watch.watcher_status(self.directory)['watcher_running'])

    def test_log_backlog_and_unavailability_do_not_hide_scheduler_attention(self):
        """Keep diagnostic reads bounded instead of draining backlog or retrying logs. """
        for mode in ('backlog', 'unavailable'):
            self.directory = Path(self.tmp.name) / mode
            runner = FakeRunner([reply(status(children=('FAILED',)))], self.clock)
            original = runner.__call__

            def with_logs(run_id, operation, child, timeout):
                """Return selected diagnostic problems after a normal status reply. """
                if operation == 'status':
                    return original(run_id, operation, child, timeout)
                if mode == 'unavailable':
                    return reply({'status': 'unknown'}, 3)
                return reply({'status': 'ok', 'operation': 'job-log', 'run_id': run_id,
                              'slurm_job_id': 100 if child is None else 101,
                              'child_key': child, 'streams': {'stdout': {'more_available': True}}})

            with watch.WatchStore(self.directory) as store:
                result = watch.Watcher(RUN_ID, store, runner=with_logs, clock=self.clock).run()
            self.assertEqual(result['reason'], 'attention')
            self.assertEqual(result['log_diagnostics'][0]['state'], mode)
            self.assertEqual(len(result['log_diagnostics']), 2)

    def test_resume_acknowledges_only_a_saved_attention_report(self):
        """Preserve an unacknowledged alert until the caller explicitly resumes. """
        sample = reply(status(children=('FAILED', 'RUNNING')))
        self.run_watch([sample], codex_check_sec=60)
        path = self.directory / 'state.json'
        saved = json.loads(path.read_text())
        self.assertEqual(saved['acknowledged'], [])
        self.assertEqual(len(saved['pending_attention']), 1)
        result, _ = self.run_watch([sample], resume=True)
        self.assertEqual(result['reason'], 'checkpoint')
        saved = json.loads(path.read_text())
        self.assertEqual(len(saved['acknowledged']), 1)
        self.assertEqual(saved['pending_attention'], [])

    def test_torn_observation_is_preserved_and_resume_starts_another_segment(self):
        """Retain incomplete local evidence without corrupting subsequent JSONL records. """
        self.run_watch([reply(status())], codex_check_sec=60)
        path = self.directory / 'observations-0001.jsonl'
        old = path.read_bytes()
        with path.open('ab') as stream:
            stream.write(b'{"incomplete":')
        result, _ = self.run_watch([reply(status('COMPLETED', ('COMPLETED',)))], resume=True)
        self.assertEqual(result['reason'], 'scheduler-terminal')
        self.assertEqual(path.read_bytes(), old + b'{"incomplete":')
        second = self.directory / 'observations-0002.jsonl'
        observation = json.loads(second.read_text().splitlines()[0])
        self.assertEqual(observation['sequence'], 2)

    def test_corrupted_scheduler_summary_is_rejected_before_a_helper_call(self):
        """Reject structurally valid JSON whose stored scheduler fields are invalid. """
        self.run_watch([reply(status())], codex_check_sec=60)
        path = self.directory / 'state.json'
        saved = json.loads(path.read_text())
        saved['last_status'] = []
        path.write_text(json.dumps(saved))
        result, runner = self.run_watch([reply(status())], resume=True)
        self.assertEqual(result['reason'], 'local-error')
        self.assertEqual(runner.calls, [])

    def test_segment_rotation_never_deletes_old_evidence(self):
        """Rotate bounded local segments and retain globally increasing sequences. """
        with watch.WatchStore(self.directory, segment_bytes=100, storage_bytes=1000) as store:
            store.observation({'payload': 'a' * 30})
            first = (self.directory / 'observations-0001.jsonl').read_bytes()
            store.observation({'payload': 'b' * 30})
            self.assertEqual((self.directory / 'observations-0001.jsonl').read_bytes(), first)
            self.assertTrue((self.directory / 'observations-0002.jsonl').exists())

    def test_disk_failure_is_reported_by_cli_without_querying_hpc(self):
        """Return an explicit local error if state cannot be saved. """
        output = io.StringIO()
        with patch.object(watch.WatchStore, 'atomic_json', side_effect=OSError('disk full')):
            with patch.object(watch.HelperRunner, '__call__') as helper, redirect_stdout(output):
                code = watch.main([RUN_ID, '--state-root', self.tmp.name])
        self.assertEqual(code, 4)
        self.assertFalse(json.loads(output.getvalue())['state_saved'])
        helper.assert_not_called()

    def test_resume_rejects_another_run_and_does_not_overwrite_its_state(self):
        """Bind local resume to the run selected on the command line. """
        self.run_watch([reply(status())], codex_check_sec=60)
        path = self.directory / 'state.json'
        saved = json.loads(path.read_text())
        saved['run_id'] = 'another-run'
        path.write_text(json.dumps(saved))
        original = path.read_bytes()
        result, runner = self.run_watch([reply(status())], resume=True)
        self.assertEqual(result['reason'], 'local-error')
        self.assertEqual(runner.calls, [])
        self.assertEqual(path.read_bytes(), original)

    def test_partial_interrupted_read_is_saved_before_handoff(self):
        """Keep received bytes when the local helper process is interrupted. """
        sample = {**reply({}), 'stdout': 'partial bytes', 'interrupted': True, 'error': 'interrupted'}
        result, _ = self.run_watch([sample])
        self.assertEqual(result['reason'], 'interrupted')
        observation = json.loads((self.directory / 'observations-0001.jsonl').read_text())
        self.assertEqual(observation['stdout'], 'partial bytes')

    def test_scheduler_retry_hint_is_respected(self):
        """Wait for the supplied accounting interval instead of retrying too soon. """
        value = status('COMPLETED', ('COMPLETED',))
        value['children'][0]['scheduler'].update(accounting_gap=True, retry_after_sec=200)
        self.run_watch([reply(value)])
        self.assertEqual(self.clock.sleeps[:2], [200, 200])

    def test_log_job_id_must_match_the_status_observation(self):
        """Reject a log reply whose run and child labels hide a different Slurm ID. """
        runner = FakeRunner([reply(status('COMPLETED', ('COMPLETED',)))], self.clock)

        def changed_log(run_id, operation, child, timeout):
            """Return valid status followed by a log for an unexpected job. """
            result = runner(run_id, operation, child, timeout)
            if operation == 'log':
                payload = json.loads(result['stdout'])
                payload['slurm_job_id'] = 999
                result['stdout'] = json.dumps(payload)
            return result

        with watch.WatchStore(self.directory) as store:
            result = watch.Watcher(RUN_ID, store, runner=changed_log, clock=self.clock).run()
        self.assertEqual(result['reason'], 'local-error')
        self.assertIn('another Slurm job ID', result['detail'])

    def test_state_symlinks_and_fifos_are_rejected(self):
        """Reject special local state files without blocking or following a link. """
        self.directory.mkdir()
        fifo = self.directory / 'fifo.json'
        watch.os.mkfifo(fifo)
        with self.assertRaises(watch.WatchError):
            watch.read_json(fifo, watch.MAX_STATE_BYTES)
        target = self.directory / 'target.json'
        target.write_text('{}')
        link = self.directory / 'linked.json'
        link.symlink_to(target)
        with self.assertRaises(OSError):
            watch.read_json(link, watch.MAX_STATE_BYTES)


class HelperBoundaryTests(unittest.TestCase):
    def test_runner_rejects_mutations_and_unsafe_identifiers(self):
        """Reject arbitrary operations before spawning any local process. """
        runner = watch.HelperRunner()
        with patch.object(watch.subprocess, 'Popen') as process:
            for operation in ('submit', 'cancel', 'release', 'finalize', 'anything'):
                with self.assertRaises(ValueError):
                    runner(RUN_ID, operation, None, 1)
            with self.assertRaises(ValueError):
                runner('../escape', 'status', None, 1)
            with self.assertRaises(ValueError):
                runner(RUN_ID, 'log', '../escape', 1)
            process.assert_not_called()

    def test_runner_times_out_and_preserves_partial_output(self):
        """Kill only the local reader and save bounded output received before timeout. """
        real_popen = subprocess.Popen
        def process(_command, **kwargs):
            """Substitute a harmless local process for the fixed installed helper. """
            return real_popen(['python3', '-u', '-c', 'import time; print("partial"); time.sleep(30)'], **kwargs)

        with patch.object(watch.subprocess, 'Popen', side_effect=process):
            with patch.object(watch.time, 'monotonic', side_effect=[0, 0, 20]):
                result = watch.HelperRunner()(RUN_ID, 'status', None, 10)
        self.assertIn('partial', result['stdout'])
        self.assertIn('timed out', result['error'])
        self.assertLess(result['returncode'], 0)

    def test_runner_stops_oversized_output(self):
        """Capture no more than the configured local stdout bound. """
        real_popen = subprocess.Popen
        def process(_command, **kwargs):
            """Emit a small excessive local response instead of contacting HPC. """
            return real_popen(['python3', '-c', 'print("x" * 10000)'], **kwargs)

        with patch.object(watch, 'MAX_STDOUT', 100), patch.object(watch.subprocess, 'Popen', side_effect=process):
            result = watch.HelperRunner()(RUN_ID, 'status', None, 5)
        self.assertEqual(len(result['stdout']), 100)
        self.assertTrue(result['local_error'])


if __name__ == '__main__':
    unittest.main()
