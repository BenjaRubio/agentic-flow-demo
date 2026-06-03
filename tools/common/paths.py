"""Filesystem paths, resolved relative to the repo root.

Layout (see AGENTS.md):
    <repo root>/
      tools/common/paths.py   <- this file
      config/
      dataset/
      .tmp/
"""
from __future__ import annotations

from pathlib import Path

# .../tools/common/paths.py -> parents[2] == repo root
REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SRC_ROOT: Path = REPO_ROOT  # backward-compatible alias

CONFIG_DIR: Path = REPO_ROOT / "config"
RULES_FILE: Path = CONFIG_DIR / "rules.yaml"
PRICING_FILE: Path = CONFIG_DIR / "pricing.yaml"

DATASET_DIR: Path = REPO_ROOT / "dataset"
DOCS_DIR: Path = DATASET_DIR / "docs"
TICKETS_DIR: Path = DATASET_DIR / "tickets"
TRAIN_TICKETS: Path = TICKETS_DIR / "tickets_train.jsonl"
TEST_TICKETS: Path = TICKETS_DIR / "tickets_test.jsonl"

TMP_DIR: Path = REPO_ROOT / ".tmp"


def ensure_tmp() -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return TMP_DIR
