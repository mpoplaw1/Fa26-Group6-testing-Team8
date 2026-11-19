# Group 6 defect report

**Application:** Group 8 Poetry issue analysis.  
**Source:** https://github.com/bala-umd/project-application-template  
**Commit:** `c6742444c327c8c780e419c0915998c3f2f152f8`  
**Test date:** November 18, 2026.  
**Environment:** Windows, Python 3.13.1. Package versions are in `requirements-testing.txt`.

The suite ran 38 tests. It recorded three failures and one error. Total statement coverage was 98%. All production modules were included. No production code was changed.

The four entries below describe separate causes. Findings in template support code are included because that code is part of the assigned application. They are not presented as changes introduced by Group 8.

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

## Limits

These tests establish behavior for controlled inputs. They do not validate every record in the course dataset. Coverage measures executed statements, not correctness. The raw suite output is in `team_6_test_failures.txt`; the raw coverage output is in `team_6_test_coverage.txt`.
