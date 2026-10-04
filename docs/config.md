# Configuring your project

Habit hooks has **two kinds of configuration files**:
- **Project config** (`.habit-hooks/config.toml`) defines which plugins to run, and provides overrides to plugin defaults.
- **Plugin configs** (`habit_hooks_<plugin>/config.toml`) define a plugin's defaults.

In most cases end users should modify the project config, but plugin level defaults use the same structure for convenience.

## Installing the plugins

For maximum compatibility between languages all sensors and guides are inside plugins. When setting up a project start by installing the plugins relevant for your project.

```bash
pip install "habit-hooks[generic,python]"            # core + generic + python plugin
pip install "habit-hooks[generic,python,typescript]" # several at once
```

The generic plugin contains language agnostic sensors and guides. Since most language-specific plugins rely on the generic plugin, installing it is strongly recommended.

## Configure Which Files Are in Scope

The `files` key takes a list of pathspec matchers (no brace expansion):

```toml
files = ["**/*.ts", "**/*.tsx"] # ✅
# files = "**/*.{ts,tsx}"        ❌ matched literally, never expanded
```

Scope flags for a single run:
- `--all` — every file the project keeps
- `--file <path>` — a single file
- `--branch [base]`, `--last <n>`, `--since <ref>` — git-derived

## Silence or demote a smell

Per-smell routing overrides live under `[smells.<name>]`; a smell with no override uses the catalogue default ([smell-vocabulary.md](smell-vocabulary.md)).

- **`severity`**: `enforced` (fails the run, exit 1) or `suggested` (coaches only, exit 0).
- **`disabled`**: drop the smell — neither coached nor counted.
- **`guide`**: use a named guide file instead of `<smell>.md`.

```toml
[smells.duplicated-code]
severity = "suggested"

[smells.redundant-type-annotation]
guide = "style-nit.md"
```

## Turn a sensor off or narrow it

A `[sensors.<name>]` block overrides a sensor the plugin defines.

- **`disabled`**: drop the sensor entirely.
- **`files`**: narrow the run's scope for this sensor alone (list form — no brace expansion). Narrows, never widens — a sensor never sees a file the run was not measuring.
- **`args`**: replace the sensor's default CLI args wholesale. Only a sensor whose `command` spells `${args}` accepts them (`line-count`, `eslint`, `knip`, `pmd`); `args` on any other sensor stops the run (exit 2). `args = []` clears a default.
- **`timeout`**: seconds a sensor may run before its run is a failed one (default 300). A plugin may declare its own default for a sensor; the project override wins. A sensor that loads a compiler per project — a language linter over a monorepo — is the case for raising it.

```toml
# Turn off a sensor the plugin ships.
[sensors.knip]
disabled = true

# Narrow the generic line-count sensor to a subset of the tree.
[sensors.line-count]
files = ["src/**/*.py"]
```

## Set the default scope

With no scope flag, the run's scope comes from `[scope]`. The flags themselves live in [habit-sensors.spec.md](habit-sensors.spec.md).

- **`changedOnly`** (default `false`): restrict a run with no scope flag to uncommitted work — staged and unstaged edits, plus untracked (non-ignored) files.
- **`autoBranchOffMain`** (default `false`): when not on `mainBranch`, default to diffing against `branchBase`; at its default a run with no scope flag scans every file the `files` globs match.
- **`branchBase`** (default `"main"`): base ref for branch-relative scoping (`--branch`, `autoBranchOffMain`). Must resolve in the checkout, or the run fails. Scoping starts at its merge base with `HEAD`, so work landed on the base after you branched is not scanned as yours.
- **`mainBranch`** (default `"main"`): the branch name on which `autoBranchOffMain` does not kick in.

## Handling smells the catalogue does not name

`uncoached` decides, once for all of them, what happens to a smell no catalogue entry covers:

- **`suggest`** (the default): coached with the generic `uncoached.md` guidance and counted, but it does not fail the run.
- **`ignore`**: dropped — neither coached nor counted.
- **`enforce`**: coached and fails the run (exit 1).

A misspelled value is rejected (exit 2), naming the key and the three values it accepts.

## Adding your own smell

A sensor may emit a smell the catalogue does not name; declared under `[smells.<name>]`, it is routed deliberately:

```toml
[smells.custom-marker]
severity = "enforced"
```

The declaration lifts the smell out of `uncoached`'s reach, so it keeps blocking however `uncoached` is set. Pair it with a sensor that emits the smell (an inline entry in the plugin's `config.toml`) and a matching `guides/custom-marker.md`.

## Run a fixer script from a guide

`[runners]` maps a guide-file extension to the command that executes it; the mapper invokes `<command> guides/<smell>.<ext>` with the finding on stdin. `.md` guides are templates and need no runner; no other extension executes unless opted in here.

```toml
[runners]
py = "python"
js = "node"
```

## A worked example

A single `.habit-hooks/config.toml` for a TypeScript project — every key below is optional:

```toml
# .habit-hooks/config.toml — all optional; an empty file means "plugin defaults".

plugins = ["generic", "typescript"]              # ordered = lookup priority; drop "generic" to disable it
transformers = ["snooze"]                         # applied to the whole run's findings, in order
files = ["**/*.ts", "**/*.tsx", "**/*.js"]        # list form — pathspec has no brace expansion
uncoached = "suggest"                             # a smell the catalogue never named: suggest | ignore | enforce

[scope]
changedOnly = false
autoBranchOffMain = true                          # NOT the default: false scans every matching file
branchBase = "main"
mainBranch = "main"

# Run non-.md guides: guide extension -> command. (.md needs none.)
[runners]
py = "python"

# Turn off a sensor the plugin ships.
[sensors.knip]
disabled = true

# Narrow the generic line-count sensor to source files.
[sensors.line-count]
files = ["src/**/*.ts"]

# Demote a smell from blocking to advisory.
[smells.duplicated-code]
severity = "suggested"

# Reuse a shared guide instead of redundant-type-annotation.md.
[smells.redundant-type-annotation]
guide = "style-nit.md"

# A project-local custom smell + the sensor that emits it (paired with
# .habit-hooks/typescript/sensors/marker.toml and guides/custom-marker.md).
[smells.custom-marker]
severity = "enforced"
```

## What a plugin declares

Plugins are also defined by their `config.toml` files.

They typically define these keys:
- **`language`**: the language its findings carry; `generic` declares none.
- **`sensors`**: the sensors it runs.
- **`transformers`**: its own transformers, applied before the findings join the run.
- **`detectors`**: the external tools its sensors need, and how to install them.

For more information read [authoring-plugins.spec.md](authoring-plugins.spec.md).

## Which tool versions run

- Sensors prefer the project's own tools: `node_modules/.bin` and `.venv/bin` are searched before `PATH` ([habit-sensors.spec.md](habit-sensors.spec.md)) — the versions your project pins are the versions that run.
- Plugins are ordinary pip packages: install core and plugins together as extras (`habit-hooks[python,typescript]`) and let the lockfile pin them, so every machine and CI run resolves the same versions.

## Precedence

When config values conflict it is resolved in the following order:
- project override takes precedence over everything else
- installed plugin settings in reverse order
- generic defaults

Config files merge field by field; any other override file replaces the plugin's file wholesale.
