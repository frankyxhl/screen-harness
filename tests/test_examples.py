from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_safari_demo_documents_target_repo_and_is_noninteractive():
    demo = (ROOT / "examples" / "expense_sop.py").read_text()

    assert "https://github.com/frankyxhl/screen-harness" in demo
    assert "safari_github_repo_demo" in demo
    assert "Safari" in demo
    assert "Google Chrome" not in demo
    assert "intro(" in demo
    assert 'render(template="training")' in demo
    assert "wait_for_user" not in demo
    assert not any("\u4e00" <= char <= "\u9fff" for char in demo)


def test_readme_documents_ci_and_demo_command():
    readme = (ROOT / "README.md").read_text()

    assert "actions/workflows/ci.yml" in readme
    assert "uv run screen-harness -c 'exec(open(\"examples/expense_sop.py\").read())'" in readme
    assert "screen-harness-dist" in readme
