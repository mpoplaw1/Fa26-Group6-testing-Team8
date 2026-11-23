# Milestone 3 testing

Group 6 tested Group 8's Poetry issue-analysis application.

Source: https://github.com/bala-umd/project-application-template

Source commit: `c6742444c327c8c780e419c0915998c3f2f152f8`.

The `main` branch contains the assigned snapshot. The `testing` branch adds the tests and reports. Production modules are unchanged. Keep the testing pull request open and unmerged for grading.

## Reproduce

Use Python 3.13. The recorded run used Python 3.13.1 on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-testing.txt
python -m coverage run -m unittest discover
python -m coverage report --omit="*/test_*.py,tests/*"
```

Run both commands from the repository root. The test command exits with status 1 because defect and conditional robustness checks fail. Run the coverage command even after that exit. Do not join these commands with `&&`.

Final Windows result: 62 tests, 14 failures, 4 errors. Statement coverage is 100% (531 of 531 statements). Branch coverage is 100% (142 of 142 branches). Failure counts include subtests.

`test_milestone3.py` and `test_milestone3_extra.py` contain the milestone suite. It uses `unittest.TestCase`, assertions, and isolated fixtures. The original pytest files remain in `tests/`. They are retained as source material and are not part of the unittest run. Do not use their results as this milestone's evidence.

## Test design

| Module | Checks |
| --- | --- |
| `issue_resolution_analysis.py` | Latest closure, fallback date, fractional days, invalid intervals, label filtering, summary statistics, volume limits, histogram and bar values |
| `contributor_activity_analysis.py` | Author totals, event types, unknown authors, distinct issues, missing users, creator-only activity, stacked chart totals |
| `discussion_trends_analysis.py` | Monthly ordering, undated comments, label thresholds, averages, tie order, empty inputs, timeline values |
| `example_analysis.py` | Filtered and unfiltered event counts, chart labels, empty dataset |
| `config.py` | Typed values, environment precedence, defaults, parent-directory search, caching, argument overrides |
| `data_loader.py` | JSON loading, cache reuse, changed file paths, missing files, malformed JSON |
| `model.py` | Field mapping, dates, defaults, invalid numbers, unknown issue states |
| `run.py` | Required arguments, short options, invalid options, dispatch, unknown features, numeric contributor names |

The integration test reads a temporary JSON file through the real loader. It executes the command-line entry point in process. It checks all three new features and both optional filters. It verifies the reported values and five saved PNG files.

Chart tests use Matplotlib's `Agg` backend. Interactive display is mocked. Calculations and chart construction run normally. Tests inspect chart values, labels, and PNG signatures.

Configuration and loader state are restored after each test. Fixtures use synthetic records. The full course dataset is not required and was not used in this run.

## Coverage and evidence

`.coveragerc` names all eight production modules. It excludes test files. Direct-execution statements remain in the denominator. The report does not hide production code to raise coverage.

Direct-module launch tests, configuration compatibility tests and a defensive report test cover the previously unexecuted paths. Every production statement and branch executed in the final run.

The two text reports contain raw command output. No lines were rewritten. Runtime duration and absolute traceback paths can differ on another machine.

Functional defects, conditional robustness findings and documented limitations are distinguished in `team_6_defect_report.md`. Failing tests assert expected or explicitly proposed robustness behavior. D9, D13 and D14 tests assert the README contract and pass. No production fix was introduced to achieve this result. They are not skipped or marked as expected failures. Several findings affect support code shipped with the template. The report does not attribute their introduction to Group 8.

## Submission

Submit these four files from the separate `deliverables` folder:

- `team_6_test_failures.txt`
- `team_6_test_coverage.txt`
- `team_6_defect_report.md`
- `team_6_testing_pr.txt`

The pull-request file must contain only the live URL. The pull request must target this repository's `main` branch from `testing`. Do not merge it before grading.
