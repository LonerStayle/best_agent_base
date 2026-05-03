"""Gemini 어댑터 — google-genai 직접, CachedContent 통합 (FR-2, FR-4, D1).

LangChain 제거 (D1 결정). 인스턴스 단위 in-memory cache map (D4).
asyncio.Lock per static_hash 로 R-1 race 완화. SDK 예외는 그대로 전파 (D6),
단 cache 생성 실패는 캐시 우회 + miss event 후 일반 호출 fallback.
"""

from __future__ import annotations

import asyncio
import os

from google import genai
from google.genai import types

from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.llm.messages import split_at_boundary
from best_agent_base.llm.profiles import DEFAULT_CHAT, ModelProfile
from best_agent_base.prompts.render import RenderContext, get_static_hash


def _build_genai_client() -> genai.Client:
    """google-genai SDK Client 인스턴스. 테스트에서 monkeypatch 가능."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다.")
    return genai.Client(api_key=api_key)


def _cache_key_for(ctx: RenderContext) -> str:
    """캐시 키 = Phase 1 의 정적 해시. 결정성 보장 (NFR-3)."""
    return get_static_hash(ctx)


class GeminiClient:
    """LLMClient 적합 Gemini 참조 구현. 인스턴스 단위 in-memory cache map (D4)."""

    def __init__(
        self,
        profile: ModelProfile = DEFAULT_CHAT,
        *,
        metrics: CacheMetrics | None = None,
    ) -> None:
        self._profile = profile
        self._metrics = metrics if metrics is not None else CacheMetrics()
        self._sdk = _build_genai_client()
        self._cache_map: dict[str, str] = {}  # static_hash → cachedContents/<id>
        self._locks: dict[str, asyncio.Lock] = {}  # per-hash race lock (R-1)
        self._last_hash: str | None = None  # HASH_CHANGE 감지용

    def _lock_for(self, key: str) -> asyncio.Lock:
        # setdefault 로 dict-level atomic — 동시 호출에서도 단일 Lock 공유 보장.
        # (R-1: get/set 사이 await 없어도 미래 refactor 가 await 추가 시 race 가능,
        #  setdefault 가 더 robust. 새 Lock 한 번 throwaway 가능하지만 무해.)
        return self._locks.setdefault(key, asyncio.Lock())

    async def _get_or_create_cached_content(
        self, key: str, static_text: str, ttl_seconds: int
    ) -> str | None:
        """캐시 조회·생성. 실패 시 None 반환 → 호출자가 캐시 우회 fallback (D6)."""
        async with self._lock_for(key):
            existing = self._cache_map.get(key)
            if existing is not None:
                return existing
            try:
                cached = await self._sdk.aio.caches.create(
                    model=self._profile.model.value,
                    config=types.CreateCachedContentConfig(
                        system_instruction=static_text,
                        ttl=f"{ttl_seconds}s",
                    ),
                )
            except Exception:
                # 캐시 생성 실패는 호출 자체를 막지 않음 (D6 fallback)
                return None
            cache_name = getattr(cached, "name", None)
            if cache_name is not None:
                self._cache_map[key] = cache_name
            return cache_name

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = split_at_boundary(ctx)
        key = _cache_key_for(ctx)

        # HASH_CHANGE 감지 (R-4 가시성). 메트릭 계약: HASH_CHANGE 는
        # *항상 같은 호출의 MISS 직전* 에 발생하는 causal 어노테이션이므로
        # 도메인 메트릭 측에서 HASH_CHANGE + MISS 를 합산하면 cache 압력 overcount.
        if self._last_hash is not None and self._last_hash != key:
            self._metrics.emit(CacheEvent.HASH_CHANGE, key)
        self._last_hash = key

        cached_name: str | None = None
        cache_hit = False

        if policy.enabled and not policy.force_invalidate:
            cached_name = self._cache_map.get(key)
            if cached_name is not None:
                cache_hit = True
                self._metrics.emit(CacheEvent.HIT, key)
        if policy.enabled and (cached_name is None or policy.force_invalidate):
            if policy.force_invalidate:
                self._cache_map.pop(key, None)
            cached_name = await self._get_or_create_cached_content(
                key, static_text, policy.ttl_seconds
            )
            self._metrics.emit(CacheEvent.MISS, key)

        # SDK 호출 — cached_content 가 있으면 system_instruction 우회, 없으면 직접 주입
        config = (
            types.GenerateContentConfig(cached_content=cached_name)
            if cached_name is not None
            else types.GenerateContentConfig(system_instruction=static_text)
        )
        result = await self._sdk.aio.models.generate_content(
            model=self._profile.model.value,
            contents=dynamic_text or " ",
            config=config,
        )

        usage = self._extract_usage(result)
        return LLMResponse(
            text=getattr(result, "text", ""),
            static_hash=key,
            cache_hit=cache_hit,
            usage=usage,
        )

    @staticmethod
    def _extract_usage(result: object) -> TokenUsage:
        meta = getattr(result, "usage_metadata", None)
        if meta is None:
            return TokenUsage(input_tokens=0, output_tokens=0)
        return TokenUsage(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            cached_tokens=getattr(meta, "cached_content_token_count", 0) or 0,
        )

    def count_tokens(self, text: str) -> int:
        # Phase 9 본격 — 현재는 conservative 추정 (단어 1.3토큰 가정)
        return int(len(text.split()) * 1.3)
