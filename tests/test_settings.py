"""Settings 단위 테스트 — pydantic-settings 기반.

검증 항목:
- (T1) GOOGLE_API_KEY 누락 시 ValidationError
- (T2) 우선순위: init > OS env > .env > 기본값
- (T3) .env 파일 로딩 정상
- (T4) 모듈 레벨 instance 가 없는지 (lazy 인스턴스화 룰 — D-12)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


def _fresh_import(monkeypatch, env: dict[str, str | None], cwd: Path | None = None):
    """깨끗한 환경에서 best_agent_base.config 재import.

    - 기존 환경변수 모두 제거 후 env 로 덮어씀 (None 인 키는 명시적 삭제)
    - sys.modules 에서 config 제거 → reload
    """
    for key in ("GOOGLE_API_KEY", "LOG_LEVEL", "DATABASE_URL", "AGENT_STATE_DIR", "REDIS_URL", "BLOB_STORE_URL"):
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    if cwd is not None:
        monkeypatch.chdir(cwd)
    sys.modules.pop("best_agent_base.config", None)
    return importlib.import_module("best_agent_base.config")


def test_missing_required_field_raises(monkeypatch):
    """T1: GOOGLE_API_KEY 누락 + .env 없으면 ValidationError."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": None}, cwd=Path("/tmp"))
    with pytest.raises(ValidationError):
        mod.Settings()


def test_init_arg_overrides_env(monkeypatch):
    """T2-a: init 인자 > env."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": "from-env"})
    settings = mod.Settings(google_api_key="from-init")
    assert settings.google_api_key == "from-init"


def test_env_overrides_default(monkeypatch):
    """T2-b: env > 기본값."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": "k", "LOG_LEVEL": "DEBUG"})
    settings = mod.Settings()
    assert settings.log_level == "DEBUG"


def test_default_values_when_optional_missing(monkeypatch):
    """T2-c: 기본값 적용 (LOG_LEVEL 미지정 → INFO)."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": "k"})
    settings = mod.Settings()
    assert settings.log_level == "INFO"
    assert settings.agent_state_dir == "./.agent_state"
    assert settings.redis_url is None
    assert settings.blob_store_url is None
    assert "postgresql+asyncpg" in settings.database_url
    assert ":5435/" in settings.database_url


def test_dotenv_file_loaded(tmp_path, monkeypatch):
    """T3: .env 파일이 로드되어야 한다."""
    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_API_KEY=from-dotenv\nLOG_LEVEL=WARNING\n")
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": None, "LOG_LEVEL": None}, cwd=tmp_path)
    settings = mod.Settings()
    assert settings.google_api_key == "from-dotenv"
    assert settings.log_level == "WARNING"


def test_no_module_level_instance(monkeypatch):
    """T4: D-12 lazy 인스턴스화 룰 — 모듈 import 만으로는 Settings() 가 호출되지 않아야 한다.

    모듈 import 자체가 GOOGLE_API_KEY 누락 환경에서 깨지지 않는지 확인.
    """
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": None}, cwd=Path("/tmp"))
    # import 자체는 성공해야 함 (모듈 레벨 글로벌 인스턴스 없음)
    assert hasattr(mod, "Settings")
    # 모듈 attribute 에 settings 인스턴스가 글로벌로 존재하지 않음
    candidates = [name for name in dir(mod) if name.lower() in {"settings_instance", "config", "settings_global"}]
    assert candidates == [], f"모듈 레벨 글로벌 인스턴스 발견: {candidates}"
