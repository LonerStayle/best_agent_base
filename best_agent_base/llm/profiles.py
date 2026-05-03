"""LLM model profiles — 모델 + 파라미터 묶음 (검증 포함).

cogito 의 노드별 파라미터 dict 패턴을 Pydantic 으로 강화:
- 잘못된 파라미터 조합은 인스턴스화 시점에 ValidationError
- 도메인은 베이스 프리셋을 그대로 쓰거나 register/override
- 베이스에는 도메인-중립한 일반 프리셋만 둔다
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from best_agent_base.llm.models import GeminiModel


class ModelProfile(BaseModel):
    """모델 호출 파라미터 묶음. 모든 LLM 인스턴스화는 이 프로파일을 통한다."""

    model_config = ConfigDict(frozen=True)

    model: GeminiModel
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, gt=0, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


DEFAULT_CHAT = ModelProfile(
    model=GeminiModel.FLASH,
    temperature=0.0,
    max_output_tokens=4096,
)

DEFAULT_REASONING = ModelProfile(
    model=GeminiModel.PRO,
    temperature=0.0,
    max_output_tokens=8192,
)
