# api/tests/test_fixtures.py
#
# Cross-cutting check of the recorded fixtures.
#
# Tested:
# - Every URL in the fixtures uses example.com
#
# What is covered:
# - Recorded payloads never carry a real host
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_fixtures.py
#
# SEE: docs/testing.md

import re
from pathlib import Path
from urllib.parse import urlsplit

TESTS = Path(__file__).parent
URL = re.compile(r"https?://[^/\s\"']+")


def test_every_url_in_the_fixtures_uses_example_com() -> None:
    files = sorted(TESTS.glob("**/fixtures/**/*.json"))
    assert files

    hosts = {
        (path.relative_to(TESTS).as_posix(), urlsplit(url).hostname)
        for path in files
        for url in URL.findall(path.read_text(encoding="utf-8"))
    }

    assert {entry for entry in hosts if entry[1] != "example.com"} == set()
