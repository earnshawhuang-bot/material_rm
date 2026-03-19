#!/usr/bin/env python3
"""Encoding guardrail checker for this repository.

Checks:
1) All tracked text-like files are valid UTF-8.
2) No Unicode replacement character (U+FFFD) appears in scanned files.
3) Critical files include required anchor text.
4) Critical files do not contain common mojibake tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


TEXT_EXTENSIONS = {
    ".html",
    ".js",
    ".css",
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".sql",
}

IGNORE_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "tmp_edge_profile",
    "tmp_edge_profile2",
}

IGNORE_FILE_PREFIXES = ("tmp_",)

# We only enforce mojibake-token detection on critical files to avoid
# false positives for normal Chinese text in other files.
CRITICAL_MOJIBAKE_RULES: dict[str, list[str]] = {
    "backend/static/index.html": [
        "\u6434\u64b3\u74e8",  # 库存 -> 搴撳瓨
        "\u935a\u3126\u669f",  # 吨数 -> 鍚ㄦ暟
        "\u93c4\u5ea3\u7c8f",  # 明细 -> 鏄庣粏
        "\u934f\u3129\u5134",  # 全部 -> 鍏ㄩ儴
        "\u5bf0\u546d\u52ed\u608a",  # 待处理 -> mojibake token
        "\u951f\u65a4\u62f7",  # 锟斤拷
    ],
}

ANCHOR_RULES: dict[str, list[str]] = {
    "README.md": [
        "RM \u5e93\u5b58\u5f02\u5e38\u5904\u7406\u534f\u540c\u5e73\u53f0",
    ],
    "backend/static/index.html": [
        "RM \u5e93\u5b58\u5206\u6790\u4e0e\u5904\u7406\u5e73\u53f0",
        "RM \u5e93\u5b58\u98ce\u9669 Dashboard",
        "\u5e93\u5b58\u660e\u7ec6",
    ],
}


@dataclass
class Issue:
    path: Path
    message: str


def should_scan(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    if any(part in IGNORE_DIR_NAMES for part in rel.parts):
        return False
    if path.name.startswith(IGNORE_FILE_PREFIXES):
        return False
    return path.suffix.lower() in TEXT_EXTENSIONS


def scan_text_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if should_scan(path, repo_root):
            files.append(path)
    return files


def validate_utf8(path: Path) -> tuple[str | None, str | None]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"not valid UTF-8: {exc}"
    return text, None


def run(repo_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    files = scan_text_files(repo_root)

    for path in files:
        text, err = validate_utf8(path)
        if err is not None:
            issues.append(Issue(path=path, message=err))
            continue
        assert text is not None

        if "\ufffd" in text:
            issues.append(Issue(path=path, message="contains replacement char U+FFFD"))

    for rel_path, anchors in ANCHOR_RULES.items():
        path = repo_root / rel_path
        if not path.exists():
            issues.append(Issue(path=path, message="missing required file for anchor checks"))
            continue
        text, err = validate_utf8(path)
        if err is not None:
            issues.append(Issue(path=path, message=err))
            continue
        assert text is not None

        for anchor in anchors:
            if anchor not in text:
                issues.append(Issue(path=path, message=f"missing anchor text: {anchor!r}"))

    for rel_path, tokens in CRITICAL_MOJIBAKE_RULES.items():
        path = repo_root / rel_path
        if not path.exists():
            continue
        text, err = validate_utf8(path)
        if err is not None:
            continue
        assert text is not None

        for token in tokens:
            if token in text:
                issues.append(Issue(path=path, message=f"contains suspicious mojibake token: {token!r}"))
                break

    return issues


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    issues = run(repo_root)
    if not issues:
        print("encoding-check: OK")
        return 0

    print(f"encoding-check: FAIL ({len(issues)} issues)")
    for issue in issues:
        rel = issue.path.relative_to(repo_root) if issue.path.exists() else issue.path
        print(f"- {rel}: {issue.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
