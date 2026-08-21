"""Public foundation files and package version."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "docs/ARCHITECTURE.md",
    "docs/EVALUATION.md",
    "docs/DEMO.md",
    "evaluation/README.md",
    "examples/demo_documents/README.md",
]


def test_required_context_files_exist() -> None:
    missing = [rel for rel in REQUIRED_DOCS if not (ROOT / rel).is_file()]
    assert missing == [], f"Missing required public docs: {missing}"


def test_readme_is_public_landing_page() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "single-user" in lowered
    assert "qualitybench_v1" in text
    assert "not a hosted saas" in lowered
    assert "hallucination-free" not in lowered
    assert "100% accurate" not in lowered
    assert "enterprise-ready" not in lowered


def test_package_version_is_defined() -> None:
    from research_assistant import __version__

    assert __version__ == "0.10.0"
