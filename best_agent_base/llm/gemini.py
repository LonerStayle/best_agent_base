"""Gemini LLM 팩토리.

제약: 모델·파라미터는 반드시 `ModelProfile` 을 통해 전달 (raw string/숫자 인자 금지).
프리셋: `DEFAULT_CHAT` (FLASH, temp=0) / `DEFAULT_REASONING` (PRO, temp=0).
도메인은 자기 프로파일을 정의해 주입.
"""

from __future__ import annotations

import os

from langchain_google_genai import ChatGoogleGenerativeAI

from best_agent_base.llm.profiles import DEFAULT_CHAT, ModelProfile


def get_gemini(profile: ModelProfile = DEFAULT_CHAT) -> ChatGoogleGenerativeAI:
    """프로파일 기반 Gemini 인스턴스 생성.

    GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경변수 필요.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다.")

    kwargs: dict = {
        "model": profile.model.value,
        "temperature": profile.temperature,
        "max_output_tokens": profile.max_output_tokens,
        "google_api_key": api_key,
    }
    if profile.top_p is not None:
        kwargs["top_p"] = profile.top_p

    return ChatGoogleGenerativeAI(**kwargs)
