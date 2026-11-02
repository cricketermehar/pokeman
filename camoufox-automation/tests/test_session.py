"""Unit tests for SessionManager."""

import json
import time
from pathlib import Path
import pytest

from src.session_manager import SessionManager, SessionValidationResult


@pytest.fixture
def temp_session_dir(tmp_path: Path) -> SessionManager:
    return SessionManager(session_dir=tmp_path)


def test_save_and_load_valid_session(temp_session_dir: SessionManager):
    future_exp = time.time() + 86400  # 1 day in future
    dummy_state = {
        "cookies": [
            {
                "name": "auth_token",
                "value": "xyz123",
                "domain": "example.com",
                "path": "/",
                "expires": future_exp,
            }
        ],
        "origins": [],
    }

    saved_path = temp_session_dir.save_session(dummy_state, session_name="test_user")
    assert saved_path.exists()

    loaded = temp_session_dir.load_session("test_user")
    assert loaded is not None
    assert len(loaded["cookies"]) == 1
    assert loaded["cookies"][0]["name"] == "auth_token"


def test_expired_session_fails_validation(temp_session_dir: SessionManager):
    past_exp = time.time() - 3600  # 1 hour ago
    expired_state = {
        "cookies": [
            {
                "name": "auth_token",
                "value": "expired_val",
                "domain": "example.com",
                "path": "/",
                "expires": past_exp,
            }
        ],
        "origins": [],
    }

    temp_session_dir.save_session(expired_state, session_name="expired_session")
    validation = temp_session_dir.validate_session_file("expired_session")

    assert not validation.is_valid
    assert "expired" in validation.reason.lower()

    # load_session should reject and invalidate it
    loaded = temp_session_dir.load_session("expired_session")
    assert loaded is None
    assert not temp_session_dir.get_session_path("expired_session").exists()


def test_corrupted_json_handled_gracefully(temp_session_dir: SessionManager):
    path = temp_session_dir.get_session_path("corrupt")
    path.write_text("{invalid_json: true", encoding="utf-8")

    validation = temp_session_dir.validate_session_file("corrupt")
    assert not validation.is_valid
    assert "malformed" in validation.reason.lower()


def test_session_name_sanitization_prevents_traversal(temp_session_dir: SessionManager):
    malicious_name = "../../../etc/passwd"
    safe_path = temp_session_dir.get_session_path(malicious_name)
    assert ".." not in safe_path.name
    assert safe_path.parent == temp_session_dir.session_dir


def test_invalidate_session_removes_file(temp_session_dir: SessionManager):
    path = temp_session_dir.save_session({"cookies": [{"name": "c", "value": "v"}]}, "to_delete")
    assert path.exists()

    temp_session_dir.invalidate_session("to_delete")
    assert not path.exists()
