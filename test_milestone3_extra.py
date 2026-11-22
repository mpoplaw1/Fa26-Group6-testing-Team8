"""Team 6 branch-coverage tests for the assigned Team 8 application.

These tests target the branches that test_milestone3.py leaves unexecuted when
coverage is run with branch measurement (``coverage run --branch``):

* the direct-launch block (``if __name__ == '__main__':``) of five modules,
* both error-tolerant loops in ``config.overwrite_from_args``,
* the defensive ``most_discussed is None`` guard in Feature 3.

It also holds two tests for problems found by running the features on the real
Poetry datasets (see real_dataset_notes.md). Those tests use small fake data
that reproduces each problem, and they fail against the current code.

They reuse the fixtures and isolation from test_milestone3.py. Every test
asserts an observable outcome; none of them changes production code.
"""
import argparse
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')

import config
import contributor_activity_analysis as contributor
import discussion_trends_analysis as discussion
import issue_resolution_analysis as resolution
from test_milestone3 import IsolatedCase, event, issue  # shared fixtures

import json

ROOT = Path(__file__).resolve().parent


def dataset_records():
    """Two issues with comments, a label and a close event (all dates in UTC)."""
    first = dict(number=1, creator='alice', labels=['bug'], state='closed',
                 title='First issue', text='body', assignees=[],
                 created_date='2026-01-01T00:00:00Z',
                 updated_date='2026-01-04T00:00:00Z',
                 url='u1', timeline_url='t1',
                 events=[event('commented', 'bob', '2026-01-02T00:00:00Z'),
                         event('closed', 'bob', '2026-01-03T00:00:00Z')])
    second = dict(first, number=2, title='Second issue',
                  events=[event('commented', 'carol', '2026-02-02T00:00:00Z')])
    return [first, second]


class TestDirectLaunch(IsolatedCase):
    """Run each module as ``python <module>.py`` and check what it produces."""

    def setUp(self):
        super().setUp()
        path = self.directory / 'issues.json'
        path.write_text(json.dumps(dataset_records()), encoding='utf-8')
        self.charts = self.directory / 'charts'
        os.environ['ENPM611_PROJECT_DATA_PATH'] = str(path)
        os.environ['ENPM611_CHART_OUTPUT_DIR'] = str(self.charts)

    def launch(self, filename):
        """Execute a module file as the main program and return its output."""
        with patch('matplotlib.pyplot.show') as show:
            _, output = self.capture(runpy.run_path, str(ROOT / filename),
                                     None, '__main__')
        return output, show

    def test_data_loader_reports_loaded_issue_count(self):
        output, _ = self.launch('data_loader.py')
        self.assertIn('Loaded 2 issues from', output)

    def test_issue_resolution_runs_and_saves_label_chart(self):
        output, _ = self.launch('issue_resolution_analysis.py')
        self.assertIn('=== Feature 1: Issue Resolution Analysis ===', output)
        # Issue 1: created Jan 1, closed Jan 3 -> 2.0 days.
        self.assertIn('bug', output)
        self.assertTrue((self.charts / 'feature1_median_by_label.png').is_file())

    def test_contributor_activity_runs_and_saves_ranking_chart(self):
        output, _ = self.launch('contributor_activity_analysis.py')
        self.assertIn('=== Feature 2: Contributor Activity Analysis ===', output)
        self.assertIn('"bob" is the most active contributor with 2 events', output)
        self.assertTrue((self.charts / 'feature2_top_contributors.png').is_file())

    def test_discussion_trends_runs_and_saves_timeline(self):
        output, _ = self.launch('discussion_trends_analysis.py')
        self.assertIn('Total comments:           2', output)
        self.assertIn('busiest month was', output)
        self.assertTrue((self.charts / 'feature3_discussion_timeline.png').is_file())

    def test_example_analysis_counts_events_and_shows_chart(self):
        output, show = self.launch('example_analysis.py')
        self.assertIn('Found 3 events across 2 issues.', output)
        show.assert_called_once()


class TestOverwriteFromArgsBranches(IsolatedCase):
    """White-box tests of both try/except loops in config.overwrite_from_args."""

    def test_python2_style_mapping_is_stored_and_none_skipped(self):
        # The first loop calls vars(args).iteritems(), which only exists on
        # Python 2 dictionaries. A mapping that provides it exercises that path.
        class LegacyMapping(dict):
            def iteritems(self):
                return iter(self.items())

        class LegacyArgs:
            pass

        args = LegacyArgs()
        args.__dict__ = LegacyMapping(user='alice', label=None)
        config.overwrite_from_args(args)
        self.assertEqual(config.get_parameter('user'), 'alice')
        self.assertNotIn('label', os.environ)

    def test_unserializable_value_is_ignored_without_crashing(self):
        # set_parameter() JSON-encodes non-string values; an object that cannot
        # be encoded raises TypeError, which overwrite_from_args swallows.
        args = argparse.Namespace(feature=3, bad=object())
        config.overwrite_from_args(args)  # must not raise
        self.assertEqual(config.get_parameter('feature'), 3)
        self.assertNotIn('bad', os.environ)


class TestDiscussionGuard(IsolatedCase):
    """The 'most discussed issue' line is skipped when no issue is reported."""

    def test_report_omits_most_discussed_line_when_none(self):
        issues = [issue(events=[event('commented', 'bob', '2026-01-02T00:00:00Z')])]
        stats = dict(total_comments=1, issue_count=1, avg_comments=1.0,
                     most_discussed=None)
        os.environ['ENPM611_CHART_OUTPUT_DIR'] = str(self.directory / 'charts')
        with patch.object(discussion.DataLoader, 'get_issues', return_value=issues), \
                patch.object(discussion, 'overall_stats', return_value=stats):
            _, output = self.capture(discussion.DiscussionTrendsAnalysis().run)
        self.assertIn('Total comments:           1', output)
        self.assertNotIn('Most discussed issue', output)
        self.assertIn('busiest month was 2026-01 with 1 comments', output)


class TestRealDataDefects(IsolatedCase):
    """Problems first seen on the real datasets, reproduced with small fake data."""

    def setUp(self):
        super().setUp()
        os.environ['ENPM611_CHART_OUTPUT_DIR'] = str(self.directory / 'charts')

    def test_bot_accounts_are_not_ranked_as_contributors(self):
        # A bot has the most events; alice is the most active person.
        items = [issue(events=[event('commented', 'github-actions[bot]'),
                               event('commented', 'github-actions[bot]'),
                               event('commented', 'github-actions[bot]'),
                               event('commented', 'alice'),
                               event('commented', 'alice'),
                               event('commented', 'bob')])]
        with patch.object(contributor.DataLoader, 'get_issues', return_value=items):
            _, output = self.capture(contributor.ContributorActivityAnalysis().run)
        self.assertIn('"alice" is the most active contributor', output)

    def test_bot_comments_do_not_decide_the_busiest_month(self):
        # People comment most in 2022-09; a bot posts more in 2024-03.
        people = [event('commented', 'alice', '2022-09-10T00:00:00Z'),
                  event('commented', 'bob', '2022-09-11T00:00:00Z')]
        bots = [event('commented', 'github-actions[bot]', f'2024-03-0{day}T00:00:00Z')
                for day in (1, 2, 3)]
        items = [issue(events=people + bots)]
        with patch.object(discussion.DataLoader, 'get_issues', return_value=items):
            _, output = self.capture(discussion.DiscussionTrendsAnalysis().run)
        self.assertIn('busiest month was 2022-09', output)

    def test_resolution_time_does_not_use_later_activity_as_close_date(self):
        # Closed issue with no recorded close date; last activity a year later.
        item = issue(created_date='2026-01-01T00:00:00Z',
                     updated_date='2027-01-01T00:00:00Z',
                     events=[event('commented', 'bob', '2026-01-02T00:00:00Z')])
        self.assertIsNone(resolution.resolution_days(item))

if __name__ == '__main__':
    unittest.main()
