"""Tests for forbidden terms static analysis check (Issue #029).

Verifies Scenario 1, Scenario 2, and Scenario 3:
- Scenario 1: Clean UI & prompt without forbidden terms
- Scenario 2: check_forbidden_terms passes on clean codebase without false positives
- Scenario 3: check_forbidden_terms detects forbidden terms and exits with code 1
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.check_forbidden_terms import (
    PROMPT_FORBIDDEN_TERMS,
    UI_FORBIDDEN_TERMS,
    check_file,
    run_check,
)


def test_scenario_2_clean_codebase_passes():
    """Scenario 2: The current codebase should pass the forbidden terms check with 0 violations."""
    repo_root = Path(__file__).resolve().parent.parent
    exit_code = run_check(repo_root)
    assert exit_code == 0, "Current codebase must pass forbidden terms check with exit code 0"


def test_scenario_2_no_false_positive_on_valid_python_source():
    """Scenario 2: Valid backend python files like qdrant_store.py or config.py must not trigger false positives."""
    repo_root = Path(__file__).resolve().parent.parent
    qdrant_store_py = repo_root / "src" / "infrastructure" / "qdrant_store.py"
    config_py = repo_root / "src" / "infrastructure" / "config.py"

    assert qdrant_store_py.exists(), "qdrant_store.py must exist"
    assert config_py.exists(), "config.py must exist"

    # qdrant_store contains 'from qdrant_client import QdrantClient'
    # It must NOT be scanned with UI_FORBIDDEN_TERMS, only PROMPT_FORBIDDEN_TERMS
    prompt_violations = check_file(qdrant_store_py, PROMPT_FORBIDDEN_TERMS)
    assert len(prompt_violations) == 0, (
        f"qdrant_store.py had unexpected violations: {prompt_violations}"
    )

    config_violations = check_file(config_py, PROMPT_FORBIDDEN_TERMS)
    assert len(config_violations) == 0, f"config.py had unexpected violations: {config_violations}"


def test_scenario_3_ui_forbidden_term_detected():
    """Scenario 3: Any forbidden UI term in a tsx file must be detected and exit with code 1."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bad_tsx = tmp_path / "BadComponent.tsx"
        bad_tsx.write_text(
            "export const Bad = () => <span>AI テクニカルチューター</span>;\n"
            "export const BadCard = () => <div>大きな4択カード</div>;\n",
            encoding="utf-8",
        )

        violations = check_file(bad_tsx, UI_FORBIDDEN_TERMS)
        assert len(violations) == 2, f"Expected 2 violations (deduplicated), got: {violations}"
        terms = [v.term for v in violations]
        assert "テクニカルチューター" in terms
        assert "チューター" not in terms  # Substring term is deduplicated
        assert "大きな4択カード" in terms

        exit_code = run_check(tmp_path, target_ui_files=[bad_tsx], target_prompt_files=[])
        assert exit_code == 1, "run_check must return 1 when UI forbidden terms are present"


def test_scenario_3_prompt_forbidden_term_detected():
    """Scenario 3: Any forbidden prompt term in llm_provider.py must be detected and exit with code 1."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bad_prompt_py = tmp_path / "llm_provider.py"
        bad_prompt_py.write_text(
            'def _build_chat_prompt():\n    return "あなたは専属チューターです。"\n',
            encoding="utf-8",
        )

        violations = check_file(bad_prompt_py, PROMPT_FORBIDDEN_TERMS)
        assert len(violations) >= 1
        assert any(v.term == "専属チューター" for v in violations)

        exit_code = run_check(tmp_path, target_ui_files=[], target_prompt_files=[bad_prompt_py])
        assert exit_code == 1, "run_check must return 1 when prompt forbidden terms are present"
