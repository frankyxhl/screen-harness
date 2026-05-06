from screen_harness.project import init_project


def test_init_project_creates_mvp_directories_and_files(tmp_path):
    init_project(tmp_path)

    assert (tmp_path / "recordings").is_dir()
    assert (tmp_path / "agent-workspace" / "agent_helpers.py").is_file()
    assert (tmp_path / "agent-workspace" / "domain-skills").is_dir()
    assert (tmp_path / "interaction-skills").is_dir()
