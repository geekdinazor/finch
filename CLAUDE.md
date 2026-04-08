# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Finch is an open-source, cross-platform GUI client for Amazon S3 and S3-compatible storage platforms, built with Python and PyQt5.

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

The `finch/` package is organized as a set of PyQt5 windows and background threads:

- **`__main__.py`** — `MainWindow(QMainWindow)`: the application shell. Hosts toolbars, a `QTreeWidget` for browsing buckets/folders/files, and dispatches to all other windows. All core S3 interactions (list buckets, upload, download, delete, presigned URLs, etc.) live here.
- **`common.py`** — Shared infrastructure:
  - `s3_session` — a **global** `boto3.session.Session()` singleton used by every module. Credentials are applied to it at login.
  - `CONFIG_PATH` — `~/.config/finch` (credentials JSON stored here).
  - `resource_path()` — resolves asset paths in both development and frozen (cx_Freeze) builds.
  - `ObjectType` enum — `BUCKET`, `FOLDER`, `FILE` used as display-role data in the tree.
  - `StringUtils` — static formatting helpers (file size, datetime, object name).
- **`credentials.py`** — `CredentialsManager` loads credentials from `credentials.json`; secrets (access keys) are stored via `keyring`. `ManageCredentialsWindow` is the UI for CRUD on credentials.
- **`filelist.py`** — `S3FileListFetchThread(QThread)`: async thread that lists S3 objects and emits `file_list_fetched` signal. Keeps the UI non-blocking during directory expansion.
- **`upload.py`** / **`download.py`** — `S3Uploader`/`UploadDialog` and `MultiDownloadProgressDialog`: threaded upload/download with progress tracking.
- **`cors.py`** / **`acl.py`** — `CORSWindow` / `ACLWindow`: standalone `QWidget` windows for per-bucket CORS and ACL management.
- **`error.py`** — `ErrorDialog` and `show_error_dialog()` helper for consistent error display with optional traceback.
- **`widgets/search.py`** — `SearchWidget`: in-tree search UI.
- **`about.py`** — `AboutWindow`.

### Key Conventions

- **QTreeWidget column layout**: column 4 (`Qt.UserRole`) holds the bucket name; column 5 (`Qt.UserRole`) holds the full S3 object key. Helper methods `get_bucket_name_from_selected_item()` and `get_object_key_from_selected_item()` in `MainWindow` abstract this.
- **Dark theme**: applied on macOS/Linux via `apply_theme()` in `common.py`; skipped on Windows due to colour incompatibilities.
- **S3 operations** always go through `s3_session.resource` or `s3_session.resource.meta.client` — never create new sessions per-call.
- **Image assets** live in `finch/img/` (PNG and SVG); always loaded through `resource_path()`.

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
