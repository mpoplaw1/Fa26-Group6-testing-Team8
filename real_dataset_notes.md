# Real dataset notes

Our unit tests use small, made-up issue records. I also wanted to see how Team 8's app behaves on the actual Poetry data, the way a normal user would run it. So I ran all three features on both datasets we were given and checked whether the results made sense.

## How I ran it

I used the `testing` branch, without changing any of Team 8's code. I ran it on my Mac (Python 3.9) with both data files:

- `poetry_issues.json`: 661 issues, mostly from 2024
- `poetry_issues_all.json`: all 5,573 issues

For each file, I pointed the app at the data, told it to save charts to a folder instead of opening windows, and ran the same five commands from the project folder. I used a separate output folder for each dataset so the charts wouldn't overwrite each other.

For `poetry_issues.json`, charts were saved to `outputs_small`:

```bash
export ENPM611_PROJECT_DATA_PATH="<path to>/poetry_issues.json"
export ENPM611_CHART_OUTPUT_DIR=outputs_small

python run.py --feature 1
python run.py --feature 1 --label kind/bug
python run.py --feature 2
python run.py --feature 2 --user abn
python run.py --feature 3
```

For `poetry_issues_all.json`, charts were saved to `outputs_all`:

```bash
export ENPM611_PROJECT_DATA_PATH="<path to>/poetry_issues_all.json"
export ENPM611_CHART_OUTPUT_DIR=outputs_all

python run.py --feature 1
python run.py --feature 1 --label kind/bug
python run.py --feature 2
python run.py --feature 2 --user abn
python run.py --feature 3
```

## Did it work?

Yes. All ten runs (five commands on each file) finished without errors, and every one saved its chart. Each folder ended up with the same five charts:

| Command | Chart file | `poetry_issues.json` | `poetry_issues_all.json` |
| --- | --- | --- | --- |
| `--feature 1` | `feature1_median_by_label.png` | `outputs_small/` | `outputs_all/` |
| `--feature 1 --label kind/bug` | `feature1_resolution_distribution.png` | `outputs_small/` | `outputs_all/` |
| `--feature 2` | `feature2_top_contributors.png` | `outputs_small/` | `outputs_all/` |
| `--feature 2 --user abn` | `feature2_user_activity.png` | `outputs_small/` | `outputs_all/` |
| `--feature 3` | `feature3_discussion_timeline.png` | `outputs_small/` | `outputs_all/` |

Here are the main results:

| | `poetry_issues.json` | `poetry_issues_all.json` |
| --- | --- | --- |
| Feature 1, fastest label | `status/triage`, 0.9 days | `kind/question`, 0.2 days |
| Feature 1, slowest label | `status/needs-reproduction`, 400.7 days (4 issues) | `status/needs-reproduction`, 329.3 days (61 issues) |
| Feature 1, `kind/bug` | 1.1 days (267 issues) | 8.8 days (2,696 issues) |
| Feature 2, top contributor | `dimbleby`, 1,306 events | `github-actions[bot]`, 9,537 events |
| Feature 2, `abn` | 407 events, mostly comments | 4,474 events, mostly unlabeling |
| Feature 3, total comments | 3,605 | 29,461 |
| Feature 3, busiest month | 2024-04, 343 comments | 2024-03, 3,767 comments |

Most of this looks reasonable. For example, questions and duplicates get closed quickly, which is what you'd expect. But two things stood out.

## Problem 1: Bots are counted as people

GitHub has automated accounts whose names end in `[bot]`. Features 2 and 3 count them the same as real people.

**Feature 2.** In `poetry_issues_all.json`, the top "contributor" is a bot. The app prints:

> "github-actions[bot]" is the most active contributor with 9537 events across the project.

`stale[bot]` also makes the top 15. In `poetry_issues.json`, `github-actions[bot]` comes in at #2.

| | `poetry_issues.json` | `poetry_issues_all.json` |
| --- | --- | --- |
| `github-actions[bot]` | #2 (591 events) | **#1** (9,537 events) |
| `stale[bot]` | #11 (28 events) | #9 (1,040 events) |

**Feature 3.** Bot comments are counted as discussion, and that changes the "busiest month" result. In `poetry_issues_all.json`, 3,451 of the 3,767 comments in the reported busiest month (2024-03) came from `github-actions[bot]`. That's 92%. If I leave bots out, the real busiest month is 2022-09, with 920 comments.

| | `poetry_issues.json` | `poetry_issues_all.json` |
| --- | --- | --- |
| Bot comments overall | 307 of 3,605 (9%) | 5,253 of 29,461 (18%) |
| Busiest month reported | 2024-04 (343) | 2024-03 (3,767) |
| Bot comments in that month | 107 (31%) | 3,451 (92%) |
| Busiest month without bots | 2024-03 (286) | 2022-09 (920) |

So the busiest month is wrong for both files. It's just much more obvious in `poetry_issues_all.json`.

## Problem 2: Feature 1 sometimes uses the "last updated" date

When a closed issue doesn't have a recorded close date, Feature 1 uses the issue's last-updated date instead. Team 8's README mentions this. The problem is that "last updated" can be long after the issue was actually closed, for example when someone comments later or a bot locks old issues. Those issues end up looking like they took years to resolve.

| | `poetry_issues.json` | `poetry_issues_all.json` |
| --- | --- | --- |
| Closed issues using the last-updated date | 20 | 223 |
| Their typical "resolution time" | 640.5 days | 1,323.9 days (about 3.6 years) |

This pushes some reported results up. I compared each label's median with the median using only issues that have a real close date:

| Label | File | App reports | Real close dates only |
| --- | --- | --- | --- |
| `kind/bug` | `poetry_issues.json` | 1.1 days | 0.9 days |
| `kind/feature` | `poetry_issues.json` | 2.1 days | 1.6 days |
| `kind/bug` | `poetry_issues_all.json` | 8.8 days | 6.7 days |
| `kind/feature` | `poetry_issues_all.json` | 71.3 days | 49.7 days |

For `kind/feature` in `poetry_issues_all.json`, the reported time is about 43% higher than the real close dates support.

## Other things I noticed (not bugs)

- **Some labels have very few issues.** In `poetry_issues.json`, `area/build-system`, `area/installer` and `status/needs-reproduction` have only 4 issues each, so the "slowest label" finding is based on just 4 issues. Feature 3 avoids this by requiring at least 3 issues per label.
- **24 comments looked low** for the most discussed issue, so I checked the raw data. 24 really is the highest.
- **The crash bugs from our unit tests don't happen with the real data.** Neither file has null labels or events, dates without a time zone, issues without a number, or number-only usernames. Those defects are still real, but they'd only show up with different data or user input.
- **The `--user` and `--label` options work** with normal values like `abn` and `kind/bug`.

## How I checked the numbers

Most numbers come straight from the app's output. For the bot numbers, I counted comments and events from the JSON files, treating names ending in `[bot]` as bots. For the "real close dates only" medians, I used Team 8's own `resolution_days()` function, but only on closed issues that have a recorded close date.

## For the defect report

I'm adding the two problems above to `team_6_defect_report.md`, each with a small unit test using made-up data:

1. Bots are counted as contributors and as discussion (Features 2 and 3).
2. Feature 1's last-updated fallback makes resolution times look longer than they were.
