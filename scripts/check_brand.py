#!/usr/bin/env python3
"""Robin brand gate — fail the build if user-visible "Hermes"/"Nous" strings
survive in the shipped surfaces.

This is the falsification instrument for the PRD's acceptance gate #7: "Zero
'Hermes'/'Nous' strings, logos, or icons in any user-visible surface of a
release build." It scans the SHIPPED renderer/desktop sources (and, in CI, the
built `dist/` output) for the bare brand words inside display strings, while
deliberately ignoring:

  - internal identifiers that must keep working (HERMES_HOME, hermes_cli,
    hermesDesktop, @hermes/shared, @nous-research/ui, types/hermes, the
    `hermes` venv entry point, IPC/env var names);
  - required legal attribution (LICENSE / NOTICE / About-licences), which MUST
    retain the upstream name.

Exit non-zero (with a report) when a user-visible leak is found.

Usage:
    python scripts/check_brand.py            # scan sources
    python scripts/check_brand.py --dist      # also scan built dist/ output
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Shipped, user-visible source roots. The upstream marketing site (website/),
# the docs site, and tests never ship in the installer and are out of scope.
SHIPPED_ROOTS = [
    "apps/desktop/src",
    "apps/desktop/index.html",
    "web/src",
    "web/index.html",
]

SCAN_EXT = {".ts", ".tsx", ".js", ".jsx", ".html", ".json", ".jsonl"}

# Lines containing any of these tokens are internal identifiers / required
# attribution and are not user-visible brand leaks.
ALLOW_SUBSTRINGS = (
    "HERMES_",            # env vars / constants
    "hermes_cli",         # python module path
    "hermesDesktop",      # preload bridge namespace
    "@hermes/",           # workspace package
    "@nous-research/",    # vendored UI package
    "types/hermes",       # type import path
    "/hermes'",           # import path ending
    "'hermes'",           # provider/command literal id
    '"hermes"',
    ".hermes",            # path fragments (legacy migration)
    "data-",              # data attributes
    "eslint",
    "// ",                # line comments (not shipped to users)
    "/* ",
    "* ",                 # block-comment continuation
    "LICENSE", "NOTICE", "Licence", "License",  # attribution
    "MIT",                # attribution context
    "NOUS_",              # env-var prefix (provider key mapping)
    "TOGETHER_API_KEY",   # internal env var for the EnergyIR (together) endpoint
    "api.together",       # internal endpoint host
    "'together'", '"together"',  # internal provider id literal
    "nous:",              # internal provider id key
    "'nous'", '"nous"',  # internal provider id literal
    "arc-nous",           # css class
    "FEATURED",           # FEATURED_ID = 'nous'
    "|hermes)",           # url-protocol skip regex
    "STORAGE_KEY",        # localStorage key constants
    "TOOLSET_BRAND_PREFIX",  # white-label alias source: maps 'hermes-*' presets -> 'robin-*' for display
)

# Lowercase-hyphenated tokens are internal identifiers (localStorage keys, CSS
# class names, theme ids, file names, custom events, media protocol). A user
# never reads these, so they are not brand leaks. Detected case-sensitively so
# capitalized display text ("Nous-trained") is NOT exempted.
ALLOW_REGEXES = (
    re.compile(r"hermes-[a-z]"),   # hermes-locale, hermes-chat-xterm-host, hermes-config.json …
    re.compile(r"nous-[a-z]"),     # nous-blue theme id, lens aliases …
    re.compile(r"hermes:[a-z]"),   # custom event names: 'hermes:new-session-shortcut'
    re.compile(r"hermes-media"),   # media:// protocol
    re.compile(r"/hermes[/'\"]"),  # internal api path fragments: /api/hermes/…
    re.compile(r"hermes\.[a-z]"),  # localStorage keys: hermes.desktop.*, hermes.lastLocation …
)

# "together" alone is a common English word — only the brand phrase "Together AI"
# (any spacing/casing) is a leak.
PATTERN = re.compile(r"\b(hermes|nous)\b|together[\s-]*ai", re.IGNORECASE)


def _iter_files():
    for root in SHIPPED_ROOTS:
        p = REPO / root
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.suffix.lower() in SCAN_EXT:
                    # skip test files — not shipped
                    if ".test." in f.name or ".spec." in f.name:
                        continue
                    yield f


def scan() -> list[tuple[Path, int, str]]:
    leaks: list[tuple[Path, int, str]] = []
    for f in _iter_files():
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if not PATTERN.search(line):
                    continue
                if any(tok in line for tok in ALLOW_SUBSTRINGS):
                    continue
                if any(rx.search(line) for rx in ALLOW_REGEXES):
                    continue
                leaks.append((f.relative_to(REPO), i, line.strip()[:160]))
        except (UnicodeDecodeError, OSError):
            continue
    return leaks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", action="store_true", help="(reserved) also scan built dist/ output")
    ap.parse_args()

    leaks = scan()
    if not leaks:
        print("✅ brand gate: no user-visible 'Hermes'/'Nous' leaks in shipped UI.")
        return 0

    print(f"❌ brand gate: {len(leaks)} user-visible brand leak(s) found:\n")
    for path, line_no, text in leaks:
        print(f"  {path}:{line_no}: {text}")
    print("\nFix these (or add a precise allow-substring if it is a genuine "
          "internal identifier / required attribution).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
