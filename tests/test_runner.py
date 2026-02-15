"""Tests for EDirect detection and subprocess execution."""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from pyentrez._exceptions import EDirectNotFoundError
from pyentrez._runner import EDirectRunner


@pytest.fixture
def fake_edirect(tmp_path):
    """Create a fake edirect directory with an executable esearch stub."""
    edirect_dir = tmp_path / "edirect"
    edirect_dir.mkdir()
    esearch = edirect_dir / "esearch"
    esearch.write_text("#!/bin/sh\necho fake")
    esearch.chmod(esearch.stat().st_mode | stat.S_IEXEC)
    return str(edirect_dir)


class TestResolution:
    def test_explicit_path(self, fake_edirect):
        runner = EDirectRunner(edirect_path=fake_edirect)
        assert runner._resolve() == fake_edirect

    def test_env_var(self, fake_edirect):
        runner = EDirectRunner()
        with patch.dict(os.environ, {"EDIRECT_PATH": fake_edirect}):
            assert runner._resolve() == fake_edirect

    def test_shutil_which(self, fake_edirect):
        runner = EDirectRunner()
        esearch_path = os.path.join(fake_edirect, "esearch")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDIRECT_PATH", None)
            with patch("shutil.which", return_value=esearch_path):
                resolved = runner._resolve()
                assert resolved == fake_edirect

    def test_home_edirect(self, fake_edirect, tmp_path):
        runner = EDirectRunner()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDIRECT_PATH", None)
            with patch("shutil.which", return_value=None):
                with patch("pathlib.Path.home", return_value=tmp_path):
                    assert runner._resolve() == fake_edirect

    def test_not_found_raises(self, tmp_path):
        runner = EDirectRunner()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDIRECT_PATH", None)
            with patch("shutil.which", return_value=None):
                with patch("pathlib.Path.home", return_value=tmp_path / "nonexistent"):
                    with pytest.raises(EDirectNotFoundError) as exc_info:
                        runner._resolve()
                    assert "Install EDirect" in str(exc_info.value)

    def test_lazy_resolution(self, fake_edirect):
        """Resolution happens on first _resolve(), not on __init__."""
        runner = EDirectRunner(edirect_path=fake_edirect)
        assert runner._resolved_dir is None
        runner._resolve()
        assert runner._resolved_dir == fake_edirect

    def test_cached_after_first_resolve(self, fake_edirect):
        runner = EDirectRunner(edirect_path=fake_edirect)
        runner._resolve()
        # Changing the explicit path doesn't matter — cached
        runner._explicit_path = "/nonexistent"
        assert runner._resolve() == fake_edirect
