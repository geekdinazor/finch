# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Finch is an open-source, cross-platform GUI client for Amazon S3 and S3-compatible storage platforms, built with Python and PySide6.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Running the App

```bash
python finch.py
# or after pip install:
finch
```

No test suite is configured for this project.

## Building Distributables

| Platform | Command |
|----------|---------|
| macOS DMG | `cxfreeze bdist_dmg` |
| Windows MSI | `scripts\build_msi.bat <version>` |
| Linux DEB | `scripts/build_deb.sh <version>` |
| Flatpak | `flatpak-builder` with `flatpak/com.furkankalkan.FinchS3.yml` |

cx_Freeze configuration lives in `pyproject.toml` under `[tool.cxfreeze]`.

## Architecture

The `finch/` package is organized into feature-based sub-packages using PySide6 and asyncio (`PySide6.QtAsyncio`):

- **`__main__.py`** — application entry point.
- **`config.py`** — `CONFIG_PATH` (`~/.config/finch`) and `resource_path()` for resolving assets in dev and frozen (cx_Freeze) builds.
- **`browser/`** — main browser UI:
  - `window.py` — `MainWindow(QMainWindow)`: application shell with toolbar and `QTreeWidget` for buckets/folders/files.
  - `model.py` — `ObjectType` enum (`BUCKET`, `FOLDER`, `FILE`) used as display-role data in the tree.
  - `about.py` — `AboutWindow`.
  - `widgets/search.py` — `SearchWidget`: in-tree search UI.
  - `widgets/spinner.py` — loading spinner widget.
  - `widgets/toolbars.py` — toolbar definitions.
- **`s3/service.py`** — `S3Service`: wraps boto3, replaces the old global `s3_session` singleton. All S3 operations go through this class.
- **`settings/`** — settings dialog and pages:
  - `settings_dialog.py` — `SettingsDialog` container.
  - `credentials/` — `CredentialsManager`, `CredentialsModel`, credentials page. Secrets stored via `keyring`.
  - `ui_settings/` — UI preferences page.
  - `log_settings/` — logging configuration page.
- **`transfers/upload.py`** / **`transfers/download.py`** — `UploadDialog` and `MultiDownloadProgressDialog` with async progress tracking.
- **`tools/cors.py`** / **`tools/acl.py`** — `CORSWindow` / `ACLWindow`: per-bucket CORS and ACL management.
- **`utils/error.py`** — `ErrorDialog` and `show_error_dialog()`.
- **`utils/text.py`** — formatting helpers (file size, datetime, object name).
- **`utils/dialogs.py`** — shared dialog utilities.
- **`utils/ui.py`** — UI helpers including `apply_theme()` for dark mode (macOS/Linux only).

### Key Conventions

- **QTreeWidget column layout**: column 4 (`Qt.UserRole`) holds the bucket name; column 5 (`Qt.UserRole`) holds the full S3 object key.
- **Dark theme**: applied on macOS/Linux via `apply_theme()` in `utils/ui.py`; skipped on Windows.
- **S3 operations** always go through `S3Service` — never instantiate boto3 sessions per-call.
- **Image assets** live in `finch/img/` (PNG and SVG); always loaded through `resource_path()` from `config.py`.

# General Coding Approach 
## Approach
- Think before acting. Read existing files before writing code.
- Be concise in output but thorough in reasoning.
- Prefer editing over rewriting whole files.
- Do not re-read files you have already read unless the file may have changed.
- Test your code before declaring done if tests defined.
- No sycophantic openers or closing fluff.
- Keep solutions simple and direct.
- User instructions always override this file.

## Output
- Structured output only: JSON, bullets, tables.
- Return code first. Explanation after, only if non-obvious.
- No prose unless the downstream consumer is a human reader.
- Every output must be parseable without post-processing.
- No inline prose. Use comments sparingly - only where logic is unclear.
- No boilerplate unless explicitly requested.

## Agent Behavior
- Execute the task. Do not narrate what you are doing.
- No status updates like "Now I will..." or "I have completed..."
- No asking for confirmation on clearly defined tasks. Use defaults.
- If a step fails: state what failed, why, and what was attempted. Stop.

## Code Rules
- Simplest working solution. No over-engineering.
- No abstractions for single-use operations.
- No speculative features or "you might also want..."
- Read the file before modifying it. Never edit blind.
- No docstrings or type annotations on code not being changed.
- No error handling for scenarios that cannot happen.
- Three similar lines is better than a premature abstraction.

## Review & Debugging Rules
- State the bug. Show the fix. Stop.
- No suggestions beyond the scope of the review.
- No compliments on the code before or after the review.
- Never speculate about a bug without reading the relevant code first.
- State what you found, where, and the fix. One pass.
- If cause is unclear: say so. Do not guess.

## Simple Formatting and Encoding
- No decorative Unicode: no smart quotes, emoji, em dashes, or ellipsis characters.
- Plain hyphens and straight quotes only.
- Natural language characters (accented letters, CJK, etc.) are fine when the content requires them.
- All strings must be safe for JSON serialization.
- Code output must be copy-paste safe.

## Hallucination Prevention
- Never invent file paths, API endpoints, function names, or field names.
- If a value is unknown: return null or "UNKNOWN". Never guess.
- If a file or resource was not read: do not reference its contents.
- Downstream systems break on hallucinated values. Accuracy over completeness.

## Token Efficiency
- Pipeline calls compound. Every token saved per call multiplies across runs.
- No explanatory text in agent output unless a human will read it.
- Return the minimum viable output that satisfies the task spec.
