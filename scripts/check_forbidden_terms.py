"""Forbidden terms static checker for IPA Exam RAG.

This script scans frontend UI source files and backend LLM prompt definitions
to mechanically prevent regression of unnatural jargon, internal specification
drafting notes, and implementation details from leaking into the user interface.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Force UTF-8 stream for cross-platform console safety
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 1. Frontend UI Forbidden Terms (Scanned on frontend/src/**/*.tsx)
UI_FORBIDDEN_TERMS: dict[str, str] = {
    "チューター": "不自然なカタカナ語・肩書。'AI' または 'AIアシスタント' を使用してください。",
    "テクニカルチューター": "不自然なカタカナ語・肩書。'AI' を使用してください。",
    "スレートダーク": "設計書・仕様書の内部デザイン用語。UIに露出させないでください。",
    "ALLOWED_EMAILS": "環境変数名の露出。'事前に利用許可されたアカウント' 等を使用してください。",
    "認証ゲート": "内部システム用語。'ログイン' を使用してください。",
    "ホワイトリスト": "内部開発用語。'利用許可された' 等を使用してください。",
    "動的更新": "内部開発用語。'更新' または '保存' を使用してください。",
    "Cloud Run": "インフラプラットフォーム名の露出。'本システム' 等を使用してください。",
    "大きな 4 択カード": "設計書の仕様書用語。UIに露出させないでください。",
    "大きな4択カード": "設計書の仕様書用語。UIに露出させないでください。",
    "自律成長": "バックエンドパイプライン用語。UIに露出させないでください。",
    "AI審査済": "内部審査用語。'AI検証済' を使用してください。",
    "自分専用": "ログイン前提下での不要・陳腐な装飾表現。削除してください。",
    "サクサク": "不要な陳腐なキャッチコピー。端的に目的のみを記述してください。",
    "お見事": "不要な感想語。'正解です' で十分です。",
    "知見ノート": "不自然な造語。'ナレッジ' を使用してください。",
}

# 2. Backend Prompt Forbidden Terms (Scanned on LLM prompt definitions)
PROMPT_FORBIDDEN_TERMS: dict[str, str] = {
    "専属チューター": "不自然な肩書表現。'学習を支援するAIアシスタント' を使用してください。",
    "チューター": "不自然なカタカナ語・肩書。'AIアシスタント' を使用してください。",
}


class Violation:
    def __init__(
        self, file_path: Path, line_number: int, line_content: str, term: str, reason: str
    ):
        self.file_path = file_path
        self.line_number = line_number
        self.line_content = line_content.strip()
        self.term = term
        self.reason = reason

    def __str__(self) -> str:
        return (
            f"[FORBIDDEN_TERM_ERROR] {self.file_path}:{self.line_number}\n"
            f"  用語: '{self.term}'\n"
            f"  理由: {self.reason}\n"
            f"  該当行: {self.line_content}"
        )


def check_file(file_path: Path, term_dict: dict[str, str]) -> list[Violation]:
    violations: list[Violation] = []
    if not file_path.exists() or not file_path.is_file():
        return violations

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)
        return violations

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        matched_terms: list[str] = [term for term in term_dict if term in line]
        if not matched_terms:
            continue

        # Filter out shorter terms that are substrings of a longer matched term on the same line
        # e.g., if 'テクニカルチューター' matched, suppress 'チューター'
        filtered_terms = [
            t
            for t in matched_terms
            if not any(other != t and t in other for other in matched_terms)
        ]

        for term in filtered_terms:
            violations.append(Violation(file_path, idx, line, term, term_dict[term]))

    return violations


def run_check(
    repo_root: Path,
    target_ui_files: list[Path] | None = None,
    target_prompt_files: list[Path] | None = None,
) -> int:
    all_violations: list[Violation] = []

    # 1. Check Frontend UI Files
    if target_ui_files is None:
        frontend_src = repo_root / "frontend" / "src"
        if frontend_src.exists():
            # Target all .tsx files (where UI components and screens are rendered)
            ui_files = [p for p in frontend_src.rglob("*.tsx") if "node_modules" not in p.parts]
        else:
            ui_files = []
    else:
        ui_files = target_ui_files

    for f in ui_files:
        all_violations.extend(check_file(f, UI_FORBIDDEN_TERMS))

    # 2. Check Backend LLM Provider / Prompt Files
    if target_prompt_files is None:
        src_dir = repo_root / "src"
        prompt_candidates = [
            src_dir / "infrastructure" / "llm_provider.py",
            src_dir / "infrastructure" / "prompts.py",
            src_dir / "application" / "prompts.py",
        ]
        prompt_files = [p for p in prompt_candidates if p.exists()]
    else:
        prompt_files = target_prompt_files

    for f in prompt_files:
        all_violations.extend(check_file(f, PROMPT_FORBIDDEN_TERMS))

    total_scanned = len(ui_files) + len(prompt_files)

    if all_violations:
        print(
            f"[ERROR] 禁止用語検査エラー: {len(all_violations)} 件の違反が検出されました。\n",
            file=sys.stderr,
        )
        for v in all_violations:
            print(str(v), file=sys.stderr)
            print("-" * 60, file=sys.stderr)
        print(
            "\n【ガイダンス】: UIおよびプロンプトに不自然なカタカナ語（チューター等）や"
            "設計書内部用語、インフラ名を露出させないでください。",
            file=sys.stderr,
        )
        return 1

    print(f"[OK] 禁止用語検査: 全 {total_scanned} ファイルを走査し、違反は 0 件でした。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check forbidden UI terms and prompt jargon.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root directory.",
    )
    args = parser.parse_args()
    return run_check(args.root)


if __name__ == "__main__":
    sys.exit(main())
