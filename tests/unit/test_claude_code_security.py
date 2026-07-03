"""S0-8 security sweep: git behavior (no auto remote/push, no PAT on disk) and
cached skills setup for the Claude Code agent."""

import shutil
from unittest.mock import MagicMock, patch

import pytest

from ai_research_engineer.agents.claude_code import agent as cc_agent


def _cmds(mock_run) -> list:
    """Extract the argv list from each recorded subprocess.run call."""
    return [c.args[0] for c in mock_run.call_args_list if c.args and isinstance(c.args[0], list)]


class TestGitNoAutoRemoteOrPush:
    def test_no_remote_no_push_without_git_config(self, tmp_path, monkeypatch):
        """With no GITHUB/remote config, git inits + commits locally but never
        adds a remote or pushes (assert on the subprocess call recorder)."""
        monkeypatch.delenv("GIT_REMOTE_URL", raising=False)
        monkeypatch.delenv("GIT_PUSH", raising=False)
        monkeypatch.setenv("GITHUB_PAT", "ghp_should_never_be_used")

        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            cc_agent._setup_git_repo(str(tmp_path))

        cmds = _cmds(mock_run)
        # Local init + commit happened.
        assert ["git", "init"] in cmds
        assert any(c[:2] == ["git", "commit"] for c in cmds), cmds
        # No remote was created and no push was attempted.
        assert not any("push" in c for c in cmds), f"push attempted: {cmds}"
        assert not any(c[:3] == ["git", "remote", "add"] for c in cmds), f"remote added: {cmds}"

    def test_push_only_when_remote_and_push_configured(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GIT_REMOTE_URL", "https://example.com/org/repo.git")
        monkeypatch.setenv("GIT_PUSH", "true")
        monkeypatch.setenv("GIT_PUSH_TOKEN", "ghp_faketoken")

        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            cc_agent._setup_git_repo(str(tmp_path))

        cmds = _cmds(mock_run)
        push = [c for c in cmds if "push" in c]
        assert len(push) == 1, cmds
        # Pushed to the configured URL via HEAD:main, and the token rides a
        # one-shot -c http.extraHeader (never `git remote add` into .git/config).
        assert "https://example.com/org/repo.git" in push[0]
        assert "HEAD:main" in push[0]
        assert not any(c[:3] == ["git", "remote", "add"] for c in cmds), f"remote persisted: {cmds}"


class TestNoPatOnDisk:
    def test_no_pat_written_to_any_file(self, tmp_path, monkeypatch):
        """With a fake PAT in env, no file under the working dir may contain it
        (the old code embedded the PAT in the remote URL -> .git/config)."""
        if shutil.which("git") is None:
            pytest.skip("git binary required for the real-filesystem PAT check")

        fake_pat = "ghp_FAKEabcdefghijklmnopqrstuvwxyz0123456789"
        monkeypatch.setenv("GITHUB_PAT", fake_pat)
        monkeypatch.setenv("GIT_PUSH_TOKEN", fake_pat)
        monkeypatch.delenv("GIT_REMOTE_URL", raising=False)
        monkeypatch.delenv("GIT_PUSH", raising=False)

        # Real git so real files (.git/config, .gitignore) are written.
        cc_agent._setup_git_repo(str(tmp_path))

        offenders = []
        for p in tmp_path.rglob("*"):
            if p.is_file():
                try:
                    if fake_pat.encode() in p.read_bytes():
                        offenders.append(str(p.relative_to(tmp_path)))
                except OSError:
                    continue
        assert not offenders, f"fake PAT leaked into files: {offenders}"


class TestSkillsCache:
    def test_skills_setup_uses_cache_second_time(self, tmp_path, monkeypatch):
        """Two setup_skills_directory calls clone the pinned repo only once; the
        second run copies from the cache."""
        cache = tmp_path / "cache" / "skills" / "pinned-sha"
        monkeypatch.setattr(cc_agent, "_skills_cache_dir", lambda: cache)

        fetches = {"n": 0}

        def fake_run(cmd, *args, **kwargs):
            # Simulate a successful clone: the fetch step populates the cache.
            if isinstance(cmd, list) and "fetch" in cmd:
                fetches["n"] += 1
                skill = cache / "scientific-skills" / "demo_skill"
                skill.mkdir(parents=True, exist_ok=True)
                (skill / "SKILL.md").write_text("demo")
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=fake_run):
            w1 = tmp_path / "w1"
            w1.mkdir()
            cc_agent.setup_skills_directory(str(w1))

            w2 = tmp_path / "w2"
            w2.mkdir()
            cc_agent.setup_skills_directory(str(w2))

        assert fetches["n"] == 1, "the skills repo must be cloned only once (cached thereafter)"
        # Both runs populated skills from the (single) cache.
        assert (w1 / ".claude" / "skills" / "demo_skill" / "SKILL.md").exists()
        assert (w2 / ".claude" / "skills" / "demo_skill" / "SKILL.md").exists()
