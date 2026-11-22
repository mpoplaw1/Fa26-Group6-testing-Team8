# Group 6 defect report

**Application:** Group 8 Poetry issue analysis.  
**Source:** https://github.com/bala-umd/project-application-template  
**Commit:** `c6742444c327c8c780e419c0915998c3f2f152f8`  
**Test date:** November 22, 2026.  
**Environment:** macOS, Python 3.9. Package versions are in `requirements-testing.txt`.

The suite ran 62 tests. It recorded 18 failures and four errors, and each one points to a defect in this report. Total statement and branch coverage was 100%. All production modules were included. No production code was changed.

The 14 entries below describe separate causes. D1 to D12 were found with small test data. D13 and D14 were found by running the features on `poetry_issues.json` and `poetry_issues_all.json`, then reproduced with small test data. Findings in template support code are included because that code is part of the assigned application. They are not presented as changes introduced by Group 8.

Run each reproduction command from the repository root after installing `requirements-testing.txt`. Each test creates its own data. The full course dataset is not needed.

## D1. Configuration drops a false default

**Module:** `config.py`, `get_parameter()`.  
**Test:** `TestConfig.test_false_default_is_preserved`.  
**Impact:** Callers receive `None` when they explicitly request a default of `False`.

**Preconditions:** The configuration is empty. The requested key is absent from the environment.

**Steps:**

1. Call `get_parameter('missing', default=False)`.
2. Assert that the result is `False`.

```text
python -m unittest test_milestone3.TestConfig.test_false_default_is_preserved
```

**Expected:** `False`. The caller supplied that default.  
**Actual:** `None`.

**Failure output:**

```text
AssertionError: None is not False
```

**Cause:** The function checks `if default`. This rejects valid false-valued defaults. Use a presence check rather than a truth-value check.

**Additional case:** `get_parameter('missing', default=0)` also returns `None`. The same truthiness check drops every falsy default. Test: `TestAdditionalDefects.test_zero_default_is_preserved`. Actual failure: `AssertionError: None != 0`.

## D2. Numeric contributor input loses its string type

**Modules:** `config.py`, `run.py`, `contributor_activity_analysis.py`.  
**Test:** `TestEntryPoint.test_numeric_contributor_name_remains_text`.  
**Impact:** Feature 2 reports no activity for a contributor whose matching events exist.

**Preconditions:** One issue has creator `"123"`. It contains one comment authored by `"123"`. Both values are strings.

**Steps:**

1. Supply `--feature 2 --user 123` to the entry point.
2. Let the normal argument-to-configuration path run.
3. Check the contributor's reported event count.

```text
python -m unittest test_milestone3.TestEntryPoint.test_numeric_contributor_name_remains_text
```

**Expected:** A profile with `Total events:         1`.  
**Actual:** `Finding: No activity was found for contributor "123".`

**Failure output:**

```text
AssertionError: 'Total events:         1' not found in '\n=== Feature 2: Contributor Activity Analysis ===\nQuestion: Who are the most active contributors, and what does their activity consist of?\nMethod: Aggregating every event authored by "123" and grouping it by event type.\nFinding: No activity was found for contributor "123".\n'
```

**Cause:** Configuration decoding converts `"123"` to integer `123`. The analysis compares that integer with string author names. Preserve textual command-line parameters through configuration handling.

**Additional cases:** The same decoding changes other text values. `true` becomes `True`, `1.0` becomes `1.0` (a float), and `null` becomes `None`, so a contributor named `null` is treated as no contributor at all. Test: `TestAdditionalDefects.test_text_like_user_names_stay_strings`. Actual failures: `True != 'true'`, `1.0 != '1.0'`, `None != 'null'`.

## D3. A new dataset path returns the previous dataset

**Module:** `data_loader.py`, `DataLoader.get_issues()`.  
**Test:** `TestLoader.test_changed_dataset_path_loads_new_dataset`.  
**Impact:** A process that switches datasets can analyze the wrong issues without an error.

**Preconditions:** Two valid JSON files exist. The first contains issue 1. The second contains issue 2. The loader cache starts empty.

**Steps:**

1. Set the configured path to the first file. Load its issues.
2. Set the configured path to the second file.
3. Construct a new `DataLoader`. Load its issues.
4. Check the returned issue numbers.

```text
python -m unittest test_milestone3.TestLoader.test_changed_dataset_path_loads_new_dataset
```

**Expected:** `[2]`, from the newly configured file.  
**Actual:** `[1]`, from the previous file.

**Failure output:**

```text
AssertionError: Lists differ: [1] != [2]

First differing element 0:
1
2

- [1]
+ [2]
```

**Cause:** The module-level `_ISSUES` cache is shared by every loader. It is not associated with a file path. Key the cache by path or invalidate it when the path changes.

**Scope:** This affects multiple loads in one process. Separate command-line processes start with a fresh cache.

## D4. The example feature crashes on an empty dataset

**Module:** `example_analysis.py`, `ExampleAnalysis.run()`.  
**Test:** `TestExample.test_empty_dataset_does_not_crash`.  
**Impact:** Feature 0 terminates with a traceback when the dataset contains no issues.

**Preconditions:** The loader returns an empty list. This is the result of loading valid JSON `[]`.

**Steps:**

1. Run `ExampleAnalysis.run()` with an empty issue list.
2. Check that it reports zero issues without raising an exception.

```text
python -m unittest test_milestone3.TestExample.test_empty_dataset_does_not_crash
```

**Expected:** A zero-issue message. Chart generation should stop or show a no-data result.  
**Actual:** The count is printed, then chart preparation raises an exception.

**Failure output:**

```text
df_hist = df.groupby(df["creator"]).value_counts().nlargest(top_n).plot(kind="bar", figsize=(14,8), title=f"Top {top_n} issue creators")
KeyError: 'creator'
```

**Cause:** An empty records list creates a DataFrame without a `creator` column. The next statement indexes that missing column. Handle the empty input before building the chart.

**Scope:** This is the retained template example, Feature 0. The new features passed their empty-input tests.

## D5. Null labels, assignees or events break loading and filtering

**Modules:** `model.py` (`Issue.from_json()`), `issue_resolution_analysis.py` (`collect_resolution_times()`).  
**Tests:** `TestAdditionalDefects.test_null_labels_and_assignees_load_as_empty_lists`, `test_null_events_load_as_empty_list`, `test_label_filter_tolerates_null_labels`.  
**Impact:** An issue record with `null` in one of these fields either loads with `None` instead of a list or stops the whole load with a `TypeError`. A label filter then crashes on the `None` labels.

**Preconditions:** A dataset record has `"labels": null`, `"assignees": null` or `"events": null`.

**Steps:**

1. Build an `Issue` from a record with `labels=None` and `assignees=None`. Check both fields.
2. Build an `Issue` from a record with `events=None`.
3. Build an `Issue` with `labels=None` and call `collect_resolution_times([issue], 'bug')`.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_null_labels_and_assignees_load_as_empty_lists test_milestone3.TestAdditionalDefects.test_null_events_load_as_empty_list test_milestone3.TestAdditionalDefects.test_label_filter_tolerates_null_labels
```

**Expected:** Missing and `null` values both load as an empty list. The label filter returns `[]`.  
**Actual:** `labels` and `assignees` stay `None`. `events=None` raises, and the label filter raises.

**Failure output:**

```text
AssertionError: None != []
TypeError: 'NoneType' object is not iterable
TypeError: argument of type 'NoneType' is not iterable
```

**Cause:** `jobj.get('labels', [])` applies its default only when the key is missing, not when the value is `null`. The list comprehension over `events` then iterates `None`. Treat `None` the same as a missing value.

## D6. Naive and timezone-aware dates cannot be compared

**Module:** `issue_resolution_analysis.py`, `resolution_days()`.  
**Test:** `TestAdditionalDefects.test_resolution_days_handles_mixed_timezone_awareness`.  
**Impact:** Feature 1 stops with a `TypeError` when a closed issue has a creation date without a timezone and a closing event with one.

**Preconditions:** A closed issue has `created_date` `2026-01-01T00:00:00` and a closed event dated `2026-01-03T00:00:00Z`.

**Steps:**

1. Build the issue described above.
2. Call `resolution_days(issue)`.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_resolution_days_handles_mixed_timezone_awareness
```

**Expected:** `2.0`.  
**Actual:** An exception.

**Failure output:**

```text
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**Cause:** `dateutil.parser.parse` returns a naive datetime for a string without an offset and an aware one for a string with one. The subtraction at `end_date - issue.created_date` does not normalize them. Treat naive values as UTC before subtracting.

**Scope:** The course dataset may use one format throughout. This affects data that mixes the two.

## D7. Issues without a valid number are counted as one issue

**Modules:** `model.py`, `contributor_activity_analysis.py`, `user_activity()`.  
**Test:** `TestAdditionalDefects.test_issues_without_numbers_are_counted_separately`.  
**Impact:** The "issues participated" figure is too low when issues have a missing or invalid number.

**Preconditions:** Two issues have a `null` number and the number `"n/a"`. The same user comments on both.

**Steps:**

1. Build both issues.
2. Call `user_activity(issues, 'u')`.
3. Check `issues_participated`.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_issues_without_numbers_are_counted_separately
```

**Expected:** `2`.  
**Actual:** `1`.

**Failure output:**

```text
AssertionError: 1 != 2
```

**Cause:** A missing or unparseable number falls back to `-1`, and `user_activity()` collects `issue.number` values in a set. Every such issue becomes the same `-1` entry. Count issue objects, or use a unique key.

## D8. Issue state matching is case-sensitive

**Module:** `model.py`, `Issue.from_json()`.  
**Tests:** `TestAdditionalDefects.test_state_parsing_accepts_upper_case`, `test_state_parsing_accepts_title_case`.  
**Impact:** A state of `CLOSED` or `Closed` loads as `None`. Resolution and contributor features then skip the issue silently.

**Preconditions:** A record has `"state": "CLOSED"` or `"state": "Closed"`.

**Steps:**

1. Build an `Issue` from each record.
2. Check `issue.state`.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_state_parsing_accepts_upper_case test_milestone3.TestAdditionalDefects.test_state_parsing_accepts_title_case
```

**Expected:** `State.closed`.  
**Actual:** `None`.

**Failure output:**

```text
AssertionError: None != <State.closed: 'closed'>
```

**Cause:** `State[state_value]` is an exact-name enum lookup, and unknown names are swallowed by `except KeyError`. Lower-case the value before the lookup.

**Scope:** This is an assumption about the data format. The provided dataset likely uses lower-case values, so this is a robustness defect.

## D9. Contributor lookup is case-sensitive

**Module:** `contributor_activity_analysis.py`, `user_activity()`.  
**Test:** `TestAdditionalDefects.test_user_lookup_ignores_case`.  
**Impact:** `--user alice` reports no activity for a contributor stored as `Alice`. The answer is silently wrong for ordinary input.

**Preconditions:** One issue is created by `Alice`. It contains one event authored by `Alice`.

**Steps:**

1. Call `user_activity(issues, 'alice')`.
2. Check `total_events`.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_user_lookup_ignores_case
```

**Expected:** `1`. GitHub logins are case-insensitive, so `alice` and `Alice` are the same account.  
**Actual:** `0`. The command-line run prints `Finding: No activity was found for contributor "alice".`

**Failure output:**

```text
AssertionError: 0 != 1
```

**Cause:** The function compares `issue.creator == user` and `event.author == user` as exact strings. Compare case-insensitively, for example with `casefold()`.

**Severity:** Medium. The input is common, and the result is wrong without any error.

## D10. A creator-only contributor gets a meaningless finding

**Module:** `contributor_activity_analysis.py`, `_analyze_single_user()`.  
**Test:** `TestAdditionalDefects.test_creator_only_user_gets_a_meaningful_finding`.  
**Impact:** For a user who opened issues but has no events, the report prints a finding that contradicts itself and an empty section, and shows no chart.

**Preconditions:** One issue is created by `dave`. It has no events.

**Steps:**

1. Run `ContributorActivityAnalysis` with `--user dave`.
2. Read the printed finding.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_creator_only_user_gets_a_meaningful_finding
```

**Expected:** A finding that describes the activity, for example that the contributor opened issues but commented on none. No event type named `none`.  
**Actual:** The report prints an empty `Events by type:` heading, then `Finding: "dave" is most active through "none" events (0 of 0).`

**Failure output:**

```text
AssertionError: '"none" events' unexpectedly found in '... Events by type:\nFinding: "dave" is most active through "none" events (0 of 0).\n'
```

**Cause:** When there are no events, the code falls back to the placeholder `('none', 0)` and still formats it into the "most active through" sentence. Branch on an empty `per_type` and print a message about issue creation instead.

**Scope:** The numbers printed above the finding are correct. The defect is in the summary line and the missing chart.

**Severity:** Low to medium.

## D11. An unknown feature number exits with status 0

**Module:** `run.py`, `main()`.  
**Test:** `TestAdditionalDefects.test_unknown_feature_exits_with_error_status`.  
**Impact:** Scripts and CI cannot tell that a run failed.

**Preconditions:** None.

**Steps:**

1. Run `python run.py --feature 99`.
2. Check the exit status.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_unknown_feature_exits_with_error_status
```

**Expected:** A non-zero exit status. The message `Unknown feature 99. Specify one of: 0, 1, 2, 3` is already correct.  
**Actual:** The message is printed and the process exits with status `0`.

**Failure output:**

```text
AssertionError: 0 == 0
```

**Cause:** `main()` prints the message and returns. The `__main__` block ignores the return value. Call `sys.exit(2)` or return a code that the entry point passes to `sys.exit`.

**Severity:** Low to medium.

## D12. The discussion timeline hides months without comments

**Module:** `discussion_trends_analysis.py`, `comments_per_month()` and `_plot_timeline()`.  
**Test:** `TestAdditionalDefects.test_timeline_keeps_months_without_comments`.  
**Impact:** The chart draws months with no comments directly next to each other. A three-year silence looks like one month, which distorts the trend.

**Preconditions:** One issue has comments dated `2020-01-15` and `2023-01-15`. No other comments exist.

**Steps:**

1. Run `DiscussionTrendsAnalysis` on that data.
2. Count the points on the plotted line.

```text
python -m unittest test_milestone3.TestAdditionalDefects.test_timeline_keeps_months_without_comments
```

**Expected:** 37 points, one per month from 2020-01 to 2023-01, with zero for the empty months.  
**Actual:** 2 points, drawn one step apart.

**Failure output:**

```text
AssertionError: 2 != 37
```

**Cause:** `comments_per_month()` returns only months that have a comment, and the chart places them on equally spaced positions. Fill the missing months with zero before plotting.

**Scope:** It matters only when the dataset has months without comments. A busy project may have few or none.

**Severity:** Low to medium.

## D13. Bot accounts are counted as contributors and as discussion

**Modules:** `contributor_activity_analysis.py` (`total_events_by_author()`, `_analyze_all_contributors()`), `discussion_trends_analysis.py` (`comments_per_month()`, `_report_timeline()`).  
**Tests:** `TestRealDataDefects.test_bot_accounts_are_not_ranked_as_contributors`, `TestRealDataDefects.test_bot_comments_do_not_decide_the_busiest_month` (in `test_milestone3_extra.py`).  
**Impact:** On the real data, Feature 2 names a bot as the most active contributor, and Feature 3 reports a "busiest month" that is mostly automated comments. Both findings are presented as facts about people.

**Found on real data:** In `poetry_issues_all.json`, Feature 2 prints `"github-actions[bot]" is the most active contributor with 9537 events across the project.` Feature 3 reports `busiest month was 2024-03 with 3767 comments`, but 3,451 of those comments (92%) are from `github-actions[bot]`. Without bots, the busiest month is 2022-09 with 920 comments. Details are in `real_dataset_notes.md`.

**Preconditions:**

- Feature 2 test: one issue with three comments by `github-actions[bot]`, two by `alice` and one by `bob`.
- Feature 3 test: one issue with two comments by people in 2022-09 and three comments by `github-actions[bot]` in 2024-03.

**Steps:**

1. Run `ContributorActivityAnalysis` with no `--user`, and read the finding.
2. Run `DiscussionTrendsAnalysis`, and read the busiest month.

```text
python -m unittest test_milestone3_extra.TestRealDataDefects.test_bot_accounts_are_not_ranked_as_contributors
python -m unittest test_milestone3_extra.TestRealDataDefects.test_bot_comments_do_not_decide_the_busiest_month
```

**Expected:** Feature 2 names `alice` as the most active contributor. Feature 3 reports 2022-09 as the busiest month.  
**Actual:** Feature 2 names `github-actions[bot]`. Feature 3 reports 2024-03.

**Failure output:**

```text
AssertionError: '"alice" is the most active contributor' not found in '... Finding: "github-actions[bot]" is the most active contributor with 3 events across the project. ...'
```

```text
AssertionError: 'busiest month was 2022-09' not found in '... Discussion spans 2022-09 to 2024-03; busiest month was 2024-03 with 3 comments. ...'
```

**Cause:** Both features count every event author the same way. Nothing separates automated accounts from people. Exclude authors whose names end in `[bot]` (or report them separately) before ranking contributors and counting discussion.

**Scope:** The counts themselves are correct. The problem is that the findings describe bot activity as human contribution and discussion.

**Severity:** Medium. The numbers are right, but the printed findings name a bot as the top contributor and report the wrong busiest month on the real data.

## D14. Feature 1 uses later activity as the close date

**Module:** `issue_resolution_analysis.py`, `resolution_days()`.  
**Test:** `TestRealDataDefects.test_resolution_time_does_not_use_later_activity_as_close_date` (in `test_milestone3_extra.py`).  
**Impact:** Closed issues without a recorded close date are measured up to their last update, which can be long after they were closed. This makes resolution times look much longer than the data supports.

**Found on real data:** In `poetry_issues_all.json`, 223 closed issues have no dated `closed` event. Feature 1 gives them a median "resolution time" of 1,323.9 days (about 3.6 years). This raises reported medians, for example `kind/feature` from 49.7 days (recorded close dates only) to 71.3 days. In `poetry_issues.json`, 20 issues are affected. Details are in `real_dataset_notes.md`.

**Preconditions:** One closed issue created on 2026-01-01, with one comment and no `closed` event. Its `updated_date` is 2027-01-01.

**Steps:**

1. Call `resolution_days()` on the issue.
2. Check the result.

```text
python -m unittest test_milestone3_extra.TestRealDataDefects.test_resolution_time_does_not_use_later_activity_as_close_date
```

**Expected:** `None`. The issue has no recorded close date, so its resolution time can't be determined.  
**Actual:** `365.0`. The time up to the last update is reported as the resolution time.

**Failure output:**

```text
AssertionError: 365.0 is not None
```

**Cause:** When no dated `closed` event exists, the function falls back to `issue.updated_date`. That date records the last activity on the issue, not when it was closed. Skip these issues (and report how many were skipped) rather than using the last update.

**Scope:** Team 8's README describes this fallback, so it is a known choice. The real data shows that it makes the reported results noticeably longer.

**Severity:** Medium. It affects 223 issues in the full dataset and makes reported resolution times noticeably too long, but it doesn't crash.

## Severity summary

High means the app crashes or loses data for a whole run. Medium means a wrong answer or a crash for one specific input. Low means a minor or unlikely problem.

| Defect | Title | Severity | Reason |
| --- | --- | --- | --- |
| D1 | Configuration drops a false default | Low | `None` and `False` behave the same in most checks, so few callers would notice. |
| D2 | Numeric contributor input loses its string type | Medium | A valid user name like `123` silently gets no activity. |
| D3 | A new dataset path returns the previous dataset | Medium | The app can analyze the wrong file with no warning. |
| D4 | The example feature crashes on an empty dataset | Low | Only the example feature is affected, and empty datasets are rare. |
| D5 | Null labels, assignees or events break loading and filtering | High | One bad record can stop the whole dataset from loading. |
| D6 | Naive and timezone-aware dates cannot be compared | Medium | Feature 1 crashes, but only when date formats are mixed. |
| D7 | Issues without a valid number are counted as one issue | Low | Only a count is off, and real issues always have numbers. |
| D8 | Issue state matching is case-sensitive | Low | GitHub always sends lowercase states, so real data isn't affected. |
| D9 | Contributor lookup is case-sensitive | Medium | Ordinary input gives a wrong answer with no error. |
| D10 | A creator-only contributor gets a meaningless finding | Low | The report reads oddly, but no numbers are wrong. |
| D11 | An unknown feature number exits with status 0 | Low | Only scripts that check the exit status are affected. |
| D12 | The discussion timeline hides months without comments | Low | The chart's spacing misleads, but the counts are correct. |
| D13 | Bot accounts are counted as contributors and as discussion | Medium | On the real data, the findings name a bot as the top contributor and the wrong busiest month. |
| D14 | Feature 1 uses later activity as the close date | Medium | 223 issues in the full dataset get resolution times that are too long. |


## Limits

These tests establish behavior for controlled inputs. They do not validate every record in the course dataset, but all three features were also run on `poetry_issues.json` and `poetry_issues_all.json` (see `real_dataset_notes.md`). Coverage measures executed statements and branches, not correctness. The raw suite output is in `team_6_test_failures.txt`; the raw coverage output is in `team_6_test_coverage.txt`.
