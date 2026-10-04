# habit-snooze — ignoring findings you have approved

When using habit-hooks, you may have findings you agree with but do not want to fix right away. habit-snooze lets you set those findings aside so you can work through warnings gradually, while unrelated findings continue to be reported. For snoozes tied to a file, the finding comes back once that file changes, so a snooze does not hide an issue indefinitely after the code has moved on; after reviewing the change, you can snooze it again.

Use `--snooze` to add snoozes, `--prune` to remove ones that no longer apply, and `--list` to see what's currently snoozed. Running `habit-snooze` on its own, with no flags, just applies the existing snoozes to filter findings — it doesn't change what's saved.

The examples below share one small project and run it through the real pipeline; the sensor is the python plugin's comment sensor, so every finding is one a real run would report:

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.ruff]
disabled = true

[sensors.deptry]
disabled = true
```

📄src/x.py
```python
total = 1 + 2
# total is 3
```

📄src/other.py
```python
ready = True
```

## Basic behaviour

`habit-snooze` is a transformer ([architecture.md](architecture.md)) that removes approved issues and passes everything else through.
By default all findings pass through.

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "non-essential-comment",
    "details": {},
    "issues": [
      {
        "key": "src/x.py",
        "details": {
          "file": "src/x.py",
          "line": 2,
          "message": "# total is 3",
          "source": "comment"
        }
      }
    ],
    "language": "python"
  }
]
```

## Snooze current issues

Snoozes are checked into the repository as `.habit-hooks/snooze.json`, so the whole team shares the same list. The default snooze key is the file name (see [sensor-interface.spec.md](sensor-interface.spec.md)), and each approval records the smells it was fed, so accepting one smell's pile does not silence the file's other smells. A key hand-written into the index as a bare string still approves every smell on that file at once.

`--snooze` adds the findings it is fed to the snooze list.

(example continued from previous section)

```bash
habit-sensors --all | habit-snooze --snooze && habit-snooze --list
```
🖥️ ✅
```text
src/x.py non-essential-comment
```

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[]
```

## Issues resurface on next edit

When you snooze an issue, habit-snooze will keep filtering it out as long as the file's contents remains the same.

(example continued from previous section)

```bash
printf '# what other.py is for\n' >> src/other.py
```

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "non-essential-comment",
    "details": {},
    "issues": [
      {
        "key": "src/other.py",
        "details": {
          "file": "src/other.py",
          "line": 2,
          "message": "# what other.py is for",
          "source": "comment"
        }
      }
    ],
    "language": "python"
  }
]
```

When the file is edited next time, the issue comes back. We recommend fixing the issue at that time, however running `--snooze` again approves the new version.

```bash
printf '# another comment\n' >> src/x.py
```

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "non-essential-comment",
    "details": {},
    "issues": [
      {
        "key": "src/other.py",
        "details": {
          "file": "src/other.py",
          "line": 2,
          "message": "# what other.py is for",
          "source": "comment"
        }
      },
      {
        "key": "src/x.py",
        "details": {
          "file": "src/x.py",
          "line": 2,
          "message": "# total is 3",
          "source": "comment"
        }
      },
      {
        "key": "src/x.py",
        "details": {
          "file": "src/x.py",
          "line": 3,
          "message": "# another comment",
          "source": "comment"
        }
      }
    ],
    "language": "python"
  }
]
```

```bash
habit-sensors --all | habit-snooze --snooze && habit-sensors --all | jq .
```
🖥️ ✅
```json
[]
```

## Remove snoozes for findings that no longer exist

Use `habit-sensors --all --no-snooze | habit-snooze --prune` when you want to remove snoozes for issues that are no longer reported. The command keeps snoozes for issues that are still present.

Both issues in `src/x.py` get fixed:

(example continued from previous section)

📄src/x.py
```python
total = 1 + 2
```

```bash
habit-sensors --all --no-snooze | habit-snooze --prune && habit-snooze --list
```
🖥️ ✅
```text
src/other.py non-essential-comment
```

## A snooze covers only the smell it was fed

(example continued from previous section)

Onboarding a project with a pile of accepted findings is the one-time use of `--snooze`, and a run reports several smells for the same file — approving the file's duplicated code must not silence its oversized functions. Feeding `--snooze` a filtered stream accepts exactly what was filtered for, and the run keeps coaching everything else. Here the project grows a second smell on a new file: ruff is re-enabled and `src/y.py` imports a module it never uses, beside a comment the comment sensor will flag.

📄.habit-hooks/config.toml
```toml
plugins = ["python"]

[sensors.deptry]
disabled = true
```

📄src/y.py
```python
import os

ready = True
# what y is for
```

```bash
habit-sensors --all | jq 'map(select(.smell == "non-essential-comment"))' | habit-snooze --snooze && habit-snooze --list
```
🖥️ ✅
```text
src/other.py non-essential-comment
src/y.py non-essential-comment
```

The unused import on `src/y.py` was never fed to `--snooze`, so the run keeps coaching it:

```bash
habit-sensors --all | jq .
```
🖥️ ✅
```json
[
  {
    "smell": "unused-import",
    "details": {},
    "issues": [
      {
        "key": "src/y.py",
        "details": {
          "file": "src/y.py",
          "line": 1,
          "column": 8,
          "message": "`os` imported but unused",
          "source": "ruff:F401"
        }
      }
    ],
    "language": "python"
  }
]
```
