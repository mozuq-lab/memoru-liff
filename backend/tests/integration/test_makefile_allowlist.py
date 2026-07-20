"""Integration tests for `backend/Makefile` signup allowlist CLI targets.

`allowlist-add` / `allowlist-approve` / `allowlist-remove` accept ENV / ID /
NOTE as `make VAR=...` command-line variables and forward them to the `aws`
CLI as JSON built by an inline `python3 -c` snippet. Command-line variables
are recursively-expanded Make variables, so a naive `export ENV ID NOTE` lets
Make re-expand `$` inside the values when constructing the child process
environment, silently eating a literal `$` (e.g. `NOTE='cost $5'` -> `cost `).
Since `$` is valid in an email local-part (RFC 5322 atext), this was a
correctness bug, not just a cosmetic one.

The fix pins the raw, unexpanded value via `$(value VAR)` into an immediate
variable (`ALLOWLIST_RAW_*`) before exporting it. These tests exercise the
real Makefile via subprocess + a fake `aws` shim (argv recorder, no network)
to prove the values survive the Make -> export -> shell -> python3 pipeline
unmodified.

design: docs/design/signup-allowlist/architecture.md 「4. 運用 CLI」節
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

# tests/integration/test_makefile_allowlist.py -> tests/integration -> tests -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
MAKEFILE = BACKEND_DIR / "Makefile"

# Fake `aws` CLI: records the argv it was called with (NUL-separated, so
# embedded whitespace/newlines in values can't corrupt parsing) and returns a
# minimal plausible response so the Makefile recipe doesn't fail.
FAKE_AWS_SCRIPT = """#!/usr/bin/env bash
set -eu
DUMP_FILE="${FAKE_AWS_ARGV_FILE:?FAKE_AWS_ARGV_FILE is not set}"
printf '%s\\0' "$@" > "$DUMP_FILE"
case "${1:-} ${2:-}" in
  "dynamodb put-item") exit 0 ;;
  "dynamodb update-item") exit 0 ;;
  "dynamodb delete-item") exit 0 ;;
  "dynamodb scan") echo "[]"; exit 0 ;;
esac
exit 0
"""


@pytest.fixture()
def fake_aws(tmp_path: Path) -> dict[str, Path]:
    """Install a fake `aws` shim at the front of PATH and return its paths."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    aws_shim = bin_dir / "aws"
    aws_shim.write_text(FAKE_AWS_SCRIPT)
    aws_shim.chmod(aws_shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return {
        "bin_dir": bin_dir,
        "argv_file": tmp_path / "argv.dump",
        "marker_file": tmp_path / "pwned-marker",
    }


def _run_make(target: str, make_args: list[str], fake_aws: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    """Run `make -C backend <target> <make_args...>` with the fake aws shim on PATH.

    make_args elements are passed as literal argv entries to the `make`
    subprocess (no shell involved), so any `$`, `"`, or `$(...)` they contain
    reaches Make exactly as written -- isolating the test from confounding
    shell-quoting behavior in the test harness itself.
    """
    env = dict(os.environ)
    env["PATH"] = f"{fake_aws['bin_dir']}:{env.get('PATH', '')}"
    env["FAKE_AWS_ARGV_FILE"] = str(fake_aws["argv_file"])
    return subprocess.run(
        ["make", "-C", str(BACKEND_DIR), target, *make_args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _read_argv(argv_file: Path) -> list[str]:
    parts = argv_file.read_bytes().split(b"\0")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    return [p.decode("utf-8") for p in parts]


def _extract_item(argv: list[str]) -> dict:
    return json.loads(argv[argv.index("--item") + 1])


class TestAllowlistAddValuePreservation:
    """`$(value)` + immediate-variable export must pass values through literally."""

    def test_single_dollar_sign_preserved_in_id_and_note(self, fake_aws: dict[str, Path]) -> None:
        result = _run_make(
            "allowlist-add",
            [
                "ENV=dev",
                "ID=user$tag@example.com",
                "NOTE=cost $5, home=$HOME",
            ],
            fake_aws,
        )
        assert result.returncode == 0, result.stderr

        item = _extract_item(_read_argv(fake_aws["argv_file"]))
        assert item["identifier"]["S"] == "email#user$tag@example.com"
        assert item["note"]["S"] == "cost $5, home=$HOME"

    def test_double_quotes_preserved_in_note(self, fake_aws: dict[str, Path]) -> None:
        result = _run_make(
            "allowlist-add",
            ["ENV=dev", "ID=friend@example.com", 'NOTE=friend "A"'],
            fake_aws,
        )
        assert result.returncode == 0, result.stderr

        item = _extract_item(_read_argv(fake_aws["argv_file"]))
        assert item["note"]["S"] == 'friend "A"'

    def test_command_substitution_in_note_is_not_executed(self, fake_aws: dict[str, Path]) -> None:
        marker = fake_aws["marker_file"]
        assert not marker.exists()

        result = _run_make(
            "allowlist-add",
            [
                "ENV=dev",
                "ID=friend2@example.com",
                f"NOTE=$(touch {marker})",
            ],
            fake_aws,
        )
        assert result.returncode == 0, result.stderr
        assert not marker.exists(), "value containing $(...) must not be executed as a command"

        item = _extract_item(_read_argv(fake_aws["argv_file"]))
        assert item["note"]["S"] == f"$(touch {marker})"

    def test_id_is_trimmed_and_lowercased(self, fake_aws: dict[str, Path]) -> None:
        result = _run_make(
            "allowlist-add",
            ["ENV=dev", "ID= Friend@Example.com "],
            fake_aws,
        )
        assert result.returncode == 0, result.stderr

        item = _extract_item(_read_argv(fake_aws["argv_file"]))
        assert item["identifier"]["S"] == "email#friend@example.com"

    def test_idp_prefixed_id_passes_through_unchanged(self, fake_aws: dict[str, Path]) -> None:
        result = _run_make(
            "allowlist-add",
            ["ENV=dev", "ID=idp#line_u1234abcd"],
            fake_aws,
        )
        assert result.returncode == 0, result.stderr

        item = _extract_item(_read_argv(fake_aws["argv_file"]))
        assert item["identifier"]["S"] == "idp#line_u1234abcd"
