"""Team 6 white-box tests of the assigned Team 8 application.

Fixtures are synthetic; no external dataset or network is required.
Defect tests deliberately assert the expected contract and remain failing.
"""
import argparse
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch, Mock

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import config
import data_loader
from model import Issue, Event, State
import issue_resolution_analysis as resolution
import contributor_activity_analysis as contributor
import discussion_trends_analysis as discussion
import example_analysis
import run


def event(kind='commented', author='alice', date='2026-01-02T00:00:00Z'):
    return dict(event_type=kind, author=author, event_date=date,
                label='bug', comment='Example comment')


def issue(number=1, **changes):
    record = dict(number=number, creator='alice', labels=['bug'], state='closed',
                  title='Example issue', text='Example body', assignees=['bob'],
                  created_date='2026-01-01T00:00:00Z',
                  updated_date='2026-01-06T00:00:00Z',
                  url='https://example.invalid/issues/1', timeline_url='timeline',
                  events=[event(), event('closed', 'bob', '2026-01-03T00:00:00Z')])
    record.update(changes)
    return Issue(record)


class IsolatedCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.old_config, self.old_issues = config._config, data_loader._ISSUES
        config._config = {}
        data_loader._ISSUES = None
        self.addCleanup(self.restore_globals)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.addCleanup(plt.close, 'all')

    def restore_globals(self):
        config._config, data_loader._ISSUES = self.old_config, self.old_issues

    def capture(self, function, *args):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = function(*args)
        return result, stream.getvalue()


class TestResolution(IsolatedCase):
    def test_latest_closure_and_fractional_day(self):
        item = issue(events=[event('closed', date='2026-01-02T00:00:00Z'),
                             event('closed', date='2026-01-04T12:00:00Z')])
        self.assertEqual(resolution.resolution_days(item), 3.5)

    def test_uncomputable_and_zero_duration(self):
        cases = [issue(state='open'), issue(created_date=None),
                 issue(events=[], updated_date=None),
                 issue(events=[], updated_date='2025-12-31T00:00:00Z')]
        for item in cases:
            with self.subTest(item=item.__dict__):
                self.assertIsNone(resolution.resolution_days(item))
        self.assertEqual(resolution.resolution_days(issue(events=[],
                         updated_date='2026-01-01T00:00:00Z')), 0)

    def test_fallback_and_label_filter(self):
        item = issue(events=[event('closed', date=None)])
        self.assertEqual(resolution.collect_resolution_times([item], 'bug'), [(item, 5)])
        self.assertEqual(resolution.collect_resolution_times([item], 'missing'), [])
        self.assertEqual(resolution.collect_resolution_times([issue(state='open')]), [])

    def test_summary_statistics(self):
        self.assertEqual(resolution.summary_stats([]), {})
        self.assertEqual(resolution.summary_stats([0, 2, 4, 10]),
                         dict(count=4, median=3, mean=4, min=0, max=10))

    def test_label_volume_limit_and_tie_order(self):
        items = [issue(labels=['z', 'a']), issue(2, labels=['z', 'b']),
                 issue(3, state='open', labels=['ignore'])]
        self.assertEqual(resolution.median_resolution_by_label(items, 2),
                         [('a', 2, 1), ('z', 2, 2)])
        self.assertEqual(resolution.median_resolution_by_label(items, 0), [])

    def test_no_data_messages(self):
        analysis = resolution.IssueResolutionAnalysis()
        for label in (None, 'missing'):
            with self.subTest(label=label), patch.object(data_loader.DataLoader, 'get_issues', return_value=[]):
                analysis.LABEL = label
                _, output = self.capture(analysis.run)
                self.assertIn('Finding: No closed issues', output)
                self.assertEqual(plt.get_fignums(), [])

    def test_chart_values_and_summary_in_both_modes(self):
        for label in (None, 'bug'):
            with self.subTest(label=label), patch.object(data_loader.DataLoader, 'get_issues', return_value=[issue()]), patch.object(plt, 'show') as show:
                config._config = {'label': label}
                _, output = self.capture(resolution.IssueResolutionAnalysis().run)
                self.assertIn('2.0 days', output)
                ax = plt.gcf().axes[0]
                self.assertTrue(ax.get_title())
                self.assertTrue(ax.get_xlabel())
                self.assertTrue(ax.get_ylabel())
                if label:
                    self.assertEqual(sum(p.get_height() for p in ax.patches), 1)
                    self.assertEqual(list(ax.lines[0].get_xdata()), [2, 2])
                else:
                    self.assertEqual([p.get_width() for p in ax.patches], [2])
                show.assert_called_once()
                plt.close('all')


class TestContributor(IsolatedCase):
    def test_totals_breakdown_and_unknown_types(self):
        items = [issue(events=[event(), event(None), event('closed', 'bob'), event(author=None)])]
        self.assertEqual(contributor.total_events_by_author(items), Counter(alice=2, bob=1))
        self.assertEqual(contributor.event_breakdown_by_author(items),
                         {'alice': Counter(commented=1, unknown=1), 'bob': Counter(closed=1)})
        self.assertEqual(contributor._categorize(Counter(commented=2, labeled=1, assigned=3)),
                         dict(commented=2, labeled=1, closed=0, other=3))

    def test_user_totals_and_distinct_issues(self):
        items = [issue(events=[event(), event(None)]), issue(2, creator='bob')]
        self.assertEqual(contributor.user_activity(items, 'alice'),
                         dict(total_events=3, per_type=Counter(commented=2, unknown=1),
                              issues_created=1, issues_participated=2))
        self.assertEqual(contributor.user_activity(items, 'missing')['total_events'], 0)

    def test_empty_unknown_and_creator_only(self):
        for items, user, expected in [([], None, 'No contributor activity'),
                                     ([issue()], 'missing', 'No activity was found'),
                                     ([issue(events=[])], 'alice', 'Issues opened:        1')]:
            with self.subTest(user=user), patch.object(data_loader.DataLoader, 'get_issues', return_value=items):
                config._config = {'user': user}
                _, output = self.capture(contributor.ContributorActivityAnalysis().run)
                self.assertIn(expected, output)
                self.assertEqual(plt.get_fignums(), [])

    def test_profile_chart_counts(self):
        config._config = {'user': 'alice'}
        with patch.object(data_loader.DataLoader, 'get_issues', return_value=[issue()]), patch.object(plt, 'show') as show:
            _, output = self.capture(contributor.ContributorActivityAnalysis().run)
            self.assertIn('Total events:         1', output)
            self.assertEqual([p.get_height() for p in plt.gcf().axes[0].patches], [1])
            show.assert_called_once()

    def test_project_chart_stacks_preserve_total(self):
        items = [issue(events=[event(), event('labeled'), event('assigned'), event('closed', 'bob')])]
        with patch.object(data_loader.DataLoader, 'get_issues', return_value=items), patch.object(plt, 'show') as show:
            _, output = self.capture(contributor.ContributorActivityAnalysis().run)
            self.assertIn('"alice" is the most active contributor with 3 events', output)
            ax = plt.gcf().axes[0]
            self.assertEqual(sum(p.get_height() for p in ax.patches), 4)
            self.assertEqual(len(ax.get_legend().get_texts()), 4)
            show.assert_called_once()


class TestDiscussion(IsolatedCase):
    def test_counts_and_chronological_buckets(self):
        items = [issue(events=[event(date='2026-03-01'), event(date='2025-12-31'),
                               event(date=None), event('closed')])]
        self.assertEqual(discussion.comment_count(items[0]), 3)
        self.assertEqual(discussion.comments_per_month(items), [('2025-12', 1), ('2026-03', 1)])

    def test_label_threshold_average_tie_and_limit(self):
        items = [issue(i, labels=['z', 'a'], events=[event()] * i) for i in range(1, 4)]
        items.append(issue(4, labels=['rare'], events=[event()] * 20))
        self.assertEqual(discussion.discussion_by_label(items), [('a', 2, 3), ('z', 2, 3)])
        self.assertEqual(discussion.discussion_by_label(items, 1), [('a', 2, 3)])

    def test_overall_statistics(self):
        items = [issue(), issue(2, events=[event()] * 3)]
        self.assertEqual(discussion.overall_stats(items),
                         dict(total_comments=4, issue_count=2, avg_comments=2,
                              most_discussed=items[1]))
        self.assertEqual(discussion.overall_stats([]),
                         dict(total_comments=0, issue_count=0, avg_comments=0,
                              most_discussed=None))

    def test_empty_or_no_comments(self):
        for items in ([], [issue(events=[])]):
            with self.subTest(items=items), patch.object(data_loader.DataLoader, 'get_issues', return_value=items):
                _, output = self.capture(discussion.DiscussionTrendsAnalysis().run)
                self.assertIn('no comment activity', output)

    def test_report_and_timeline_chart(self):
        items = [issue(i) for i in range(3)]
        with patch.object(data_loader.DataLoader, 'get_issues', return_value=items), patch.object(plt, 'show') as show:
            _, output = self.capture(discussion.DiscussionTrendsAnalysis().run)
            self.assertIn('avg 1.00 comments per issue', output)
            self.assertIn('2026-01', output)
            ax = plt.gcf().axes[0]
            self.assertEqual(list(ax.lines[0].get_ydata()), [3])
            self.assertEqual(ax.get_ylabel(), 'Number of comments')
            show.assert_called_once()

    def test_undated_comments_and_below_threshold(self):
        with patch.object(data_loader.DataLoader, 'get_issues', return_value=[issue(events=[event(date=None)])]), patch.object(plt, 'show') as show:
            _, output = self.capture(discussion.DiscussionTrendsAnalysis().run)
            self.assertIn('Total comments:           1', output)
            self.assertNotIn('most discussed first', output)
            show.assert_not_called()


class TestCharts(IsolatedCase):
    def test_each_analysis_saves_a_real_png(self):
        config._config = {'ENPM611_CHART_OUTPUT_DIR': str(self.directory / 'charts')}
        for cls in (resolution.IssueResolutionAnalysis, contributor.ContributorActivityAnalysis,
                    discussion.DiscussionTrendsAnalysis):
            with self.subTest(analysis=cls.__name__):
                fig, ax = plt.subplots()
                ax.plot([1, 2], [3, 4])
                result, output = self.capture(cls()._finish_chart, fig, cls.__name__ + '.png')
                self.assertTrue(Path(result).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertIn('Chart saved to', output)
                self.assertFalse(plt.fignum_exists(fig.number))


class TestConfig(IsolatedCase):
    def test_typed_conversion(self):
        for value, expected in [(None, None), (3, 3), ('false', False), ('12', 12),
                                ('[1,2]', [1, 2]), ('plain', 'plain')]:
            with self.subTest(value=value):
                self.assertEqual(config.convert_to_typed_value(value), expected)

    def test_roundtrip_env_precedence_and_defaults(self):
        config._config = {'key': 'file'}
        self.assertEqual(config.get_parameter('key'), 'file')
        for value in ('text', 7, {'a': True}):
            config.set_parameter('key', value)
            self.assertEqual(config.get_parameter('key'), value)
        self.assertIsNone(config.get_parameter('missing'))
        self.assertEqual(config.get_parameter('missing', 'fallback'), 'fallback')

    def test_false_default_is_preserved(self):
        self.assertIs(config.get_parameter('missing', default=False), False)

    def test_load_config_once_and_no_config(self):
        path = self.directory / 'config.json'
        path.write_text('{"key": 4}', encoding='utf-8')
        config._config = None
        with patch.object(config, '_get_default_path', return_value=str(path)) as search:
            self.assertEqual(config.get_parameter('key'), 4)
            self.assertEqual(config.get_parameter('key'), 4)
            search.assert_called_once()
        config._config = None
        with patch.object(config, '_get_default_path', return_value=None):
            self.assertIsNone(config.get_parameter('absent'))
            self.assertEqual(config._config, {})

    def test_parent_search_and_missing_file(self):
        parent = self.directory / 'parent'
        child = parent / 'child'
        child.mkdir(parents=True)
        path = parent / 'config.json'
        path.write_text('{}', encoding='utf-8')
        with patch.object(config.os, 'getcwd', return_value=str(child)):
            self.assertEqual(config._get_default_path(), str(path))
        with patch.object(config.os.path, 'isfile', return_value=False):
            self.assertIsNone(config._get_default_path())

    def test_args_store_values_but_skip_none(self):
        config.overwrite_from_args(argparse.Namespace(feature=2, user=None, label='bug'))
        self.assertEqual(config.get_parameter('feature'), 2)
        self.assertEqual(config.get_parameter('label'), 'bug')
        self.assertNotIn('user', os.environ)


class TestModel(IsolatedCase):
    def test_issue_and_event_fields(self):
        item = issue()
        self.assertEqual((item.number, item.creator, item.labels, item.state),
                         (1, 'alice', ['bug'], State.closed))
        self.assertEqual((item.title, item.text, item.assignees),
                         ('Example issue', 'Example body', ['bob']))
        self.assertEqual(item.timeline_url, 'timeline')
        self.assertEqual(item.created_date.year, 2026)
        self.assertEqual(item.updated_date.day, 6)
        self.assertEqual(item.events[0].comment, 'Example comment')
        self.assertEqual(item.events[0].label, 'bug')
        self.assertEqual(item.events[0].event_date.day, 2)

    def test_missing_invalid_and_default_values(self):
        self.assertEqual(Issue().number, -1)
        self.assertIsNone(Event(None).event_date)
        item = issue(number='not-a-number', state='unexpected',
                     created_date='bad', updated_date=None, events=[event(date='bad')])
        self.assertEqual(item.number, -1)
        self.assertIsNone(item.state)
        self.assertIsNone(item.created_date)
        self.assertIsNone(item.updated_date)
        self.assertIsNone(item.events[0].event_date)
        self.assertIsNone(Issue({}).state)
        self.assertEqual(Issue({}).events, [])


class TestLoader(IsolatedCase):
    def write_data(self, name, number):
        path = self.directory / name
        path.write_text(json.dumps([{'number': number, 'state': 'open', 'events': []}]), encoding='utf-8')
        return str(path)

    def test_load_and_reuse_cache(self):
        config._config = {'ENPM611_PROJECT_DATA_PATH': self.write_data('one.json', 1)}
        loader = data_loader.DataLoader()
        loaded, output = self.capture(loader.get_issues)
        self.assertEqual(loaded[0].number, 1)
        self.assertIn('Loaded 1 issues', output)
        with patch.object(loader, '_load', side_effect=AssertionError('Reloaded')):
            self.assertIs(loader.get_issues(), loaded)

    def test_missing_and_malformed_file(self):
        config._config = {'ENPM611_PROJECT_DATA_PATH': str(self.directory / 'absent.json')}
        with self.assertRaises(FileNotFoundError):
            data_loader.DataLoader().get_issues()
        path = self.directory / 'bad.json'
        path.write_text('not JSON', encoding='utf-8')
        config._config['ENPM611_PROJECT_DATA_PATH'] = str(path)
        with self.assertRaises(json.JSONDecodeError):
            data_loader.DataLoader().get_issues()

    def test_changed_dataset_path_loads_new_dataset(self):
        config.set_parameter('ENPM611_PROJECT_DATA_PATH', self.write_data('one.json', 1))
        self.capture(data_loader.DataLoader().get_issues)
        config.set_parameter('ENPM611_PROJECT_DATA_PATH', self.write_data('two.json', 2))
        loaded, _ = self.capture(data_loader.DataLoader().get_issues)
        self.assertEqual([item.number for item in loaded], [2])


class TestEntryPoint(IsolatedCase):
    def test_real_file_to_cli_to_saved_charts(self):
        records = [dict(number=i, creator='alice', labels=['bug'], state='closed',
                        created_date='2026-01-01T00:00:00Z',
                        updated_date='2026-01-03T00:00:00Z', title='Integration fixture',
                        events=[event(), event('closed', 'bob', '2026-01-03T00:00:00Z')])
                   for i in range(1, 4)]
        path = self.directory / 'fixture.json'
        path.write_text(json.dumps(records), encoding='utf-8')
        cases = [(1, [], 'feature1_median_by_label.png', '2.0 days'),
                 (1, ['--label', 'bug'], 'feature1_resolution_distribution.png', 'Resolved issues labeled "bug": 3'),
                 (2, [], 'feature2_top_contributors.png', 'with 3 events'),
                 (2, ['--user', 'alice'], 'feature2_user_activity.png', 'Total events:         3'),
                 (3, [], 'feature3_discussion_timeline.png', 'Total comments:           3')]
        for feature, extra, filename, expected in cases:
            with self.subTest(feature=feature, extra=extra):
                data_loader._ISSUES = None
                config._config = {}
                chart_dir = self.directory / str(feature) / ('filtered' if extra else 'all')
                env = dict(ENPM611_PROJECT_DATA_PATH=str(path), ENPM611_CHART_OUTPUT_DIR=str(chart_dir))
                with patch.dict(os.environ, env, clear=True), patch('sys.argv', ['run.py', '--feature', str(feature)] + extra):
                    _, output = self.capture(runpy.run_module, 'run', None, '__main__')
                self.assertIn('Loaded 3 issues', output)
                self.assertIn(expected, output)
                self.assertTrue((chart_dir / filename).read_bytes().startswith(b'\x89PNG'))

    def test_parse_short_and_long_arguments(self):
        for argv in (['run.py', '--feature', '1', '--label', 'bug', '--user', 'alice'],
                     ['run.py', '-f', '1', '-l', 'bug', '-u', 'alice']):
            with self.subTest(argv=argv), patch('sys.argv', argv):
                self.assertEqual(vars(run.parse_args()), dict(feature=1, user='alice', label='bug'))

    def test_parser_rejects_missing_and_noninteger_feature(self):
        for argv in (['run.py'], ['run.py', '--feature', 'abc']):
            with self.subTest(argv=argv), patch('sys.argv', argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                run.parse_args()
            self.assertEqual(raised.exception.code, 2)

    def test_dispatches_every_feature(self):
        for feature in range(4):
            factory = Mock()
            with self.subTest(feature=feature), patch.dict(run.FEATURES, {feature: factory}), patch('sys.argv', ['run.py', '-f', str(feature)]):
                run.main()
                factory.assert_called_once_with()
                factory.return_value.run.assert_called_once_with()
                self.assertEqual(config.get_parameter('feature'), feature)

    def test_unknown_feature_reports_choices(self):
        with patch('sys.argv', ['run.py', '-f', '99']):
            _, output = self.capture(run.main)
            self.assertIn('Unknown feature 99', output)
            self.assertIn('0, 1, 2, 3', output)

    def test_numeric_contributor_name_remains_text(self):
        with patch('sys.argv', ['run.py', '-f', '2', '--user', '123']), patch.object(data_loader.DataLoader, 'get_issues', return_value=[issue(creator='123', events=[event(author='123')])]), patch.object(plt, 'show'):
            _, output = self.capture(run.main)
            self.assertIn('Total events:         1', output)


class TestExample(IsolatedCase):
    def test_example_filtered_and_unfiltered_totals(self):
        for user, expected in [(None, 'Found 2 events across 1 issues.'),
                               ('alice', 'Found 1 events across 1 issues for alice.')]:
            with self.subTest(user=user), patch.object(data_loader.DataLoader, 'get_issues', return_value=[issue()]), patch.object(plt, 'show') as show:
                config._config = {'user': user}
                _, output = self.capture(example_analysis.ExampleAnalysis().run)
                self.assertIn(expected, output)
                self.assertEqual(plt.gcf().axes[0].get_ylabel(), '# of issues created')
                show.assert_called_once()
                plt.close('all')

    def test_empty_dataset_does_not_crash(self):
        with patch.object(data_loader.DataLoader, 'get_issues', return_value=[]), patch.object(plt, 'show'):
            _, output = self.capture(example_analysis.ExampleAnalysis().run)
            self.assertIn('Found 0 events across 0 issues.', output)


class TestAdditionalDefects(IsolatedCase):
    """Defects found by Ashish test pass (D5-D8, plus extra D1/D2 cases).

    Each test asserts the expected contract and fails against the current code.
    """

    # D2 (extra cases): configuration decodes text that looks like JSON.
    def test_text_like_user_names_stay_strings(self):
        for value in ('true', 'null', '1.0'):
            with self.subTest(value=value):
                os.environ['user'] = value
                self.assertEqual(config.get_parameter('user'), value)

    # D1 (extra case): a falsy default other than False is also dropped.
    def test_zero_default_is_preserved(self):
        self.assertEqual(config.get_parameter('missing', default=0), 0)

    # D5: null labels, assignees and events in the dataset.
    def test_null_labels_and_assignees_load_as_empty_lists(self):
        item = issue(labels=None, assignees=None)
        self.assertEqual(item.labels, [])
        self.assertEqual(item.assignees, [])

    def test_null_events_load_as_empty_list(self):
        self.assertEqual(issue(events=None).events, [])

    def test_label_filter_tolerates_null_labels(self):
        item = issue(labels=None)
        self.assertEqual(resolution.collect_resolution_times([item], 'bug'), [])

    # D6: naive and timezone-aware datetimes are mixed in one calculation.
    def test_resolution_days_handles_mixed_timezone_awareness(self):
        item = issue(created_date='2026-01-01T00:00:00',
                     events=[event('closed', date='2026-01-03T00:00:00Z')])
        self.assertEqual(resolution.resolution_days(item), 2.0)

    # D7: issues with missing or invalid numbers all collapse to -1.
    def test_issues_without_numbers_are_counted_separately(self):
        items = [issue(number=None, creator='x', events=[event(author='u')]),
                 issue(number='n/a', creator='x', events=[event(author='u')])]
        self.assertEqual(contributor.user_activity(items, 'u')['issues_participated'], 2)

    # D8: the state value is matched case-sensitively.
    def test_state_parsing_accepts_upper_case(self):
        self.assertEqual(issue(state='CLOSED').state, State.closed)

    def test_state_parsing_accepts_title_case(self):
        self.assertEqual(issue(state='Closed').state, State.closed)


if __name__ == '__main__':
    unittest.main()
