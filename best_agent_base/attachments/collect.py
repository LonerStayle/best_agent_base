"""collect_attachments — 3그룹 병렬 + null 필터 + system-reminder wrap (FR-3, FR-4).

D4: <system-reminder> wrap 은 베이스 책임.
D5: 단일 함수 + user_input=None 분기.
D9: asyncio.wait(timeout=1.0, ALL_COMPLETED) + pending cancel + 개별 try/except → None.
    spec 의 wait_for(gather) 는 타임아웃 시 부분 결과 손실 → wait() 로 변경 (test_timeout_drops_slow_keeps_fast 가 fast 결과 보존 요구).
D10: ctx.is_subagent=True 시 MAIN_THREAD 자동 제외.

CC `messages.ts:3098` wrap 형식 그대로.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from best_agent_base.attachments.gates import is_gated
from best_agent_base.attachments.protocol import Attachment, AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.messages import Message, TextBlock
from best_agent_base.prompts.render import RenderContext

COLLECT_TIMEOUT_SECONDS = 1.0


def _wrap_system_reminder(text: str) -> str:
    """CC messages.ts:3098 형식 그대로."""
    return f"<system-reminder>\n{text}\n</system-reminder>"


def _select_groups(*, user_input: str | None, is_subagent: bool) -> list[AttachmentGroup]:
    groups: list[AttachmentGroup] = []
    if user_input is not None:
        groups.append(AttachmentGroup.USER_INPUT)
    groups.append(AttachmentGroup.ALL_THREAD)
    if not is_subagent:
        groups.append(AttachmentGroup.MAIN_THREAD)
    return groups


async def _safe_build(att: Attachment, ctx: RenderContext) -> str | None:
    """개별 어태치먼트 build() 실패는 None 으로 흡수 (NFR-3 / R-7)."""
    try:
        return await att.build(ctx)
    except Exception:
        return None


def _attachments_in(groups: Iterable[AttachmentGroup], tool_pool: frozenset[str]) -> list[Attachment]:
    """그룹별 어태치먼트 + 도구 풀 게이트 통과한 것만 반환 (FR-9)."""
    out: list[Attachment] = []
    for g in groups:
        for att in attachment_registry.all_in_group(g):
            if not is_gated(att.name, tool_pool):
                out.append(att)
    return out


async def collect_attachments(
    ctx: RenderContext,
    *,
    user_input: str | None,
) -> list[Message]:
    """3그룹 어태치먼트 병렬 수집 + null 필터 + system-reminder wrap.

    user_input=str  → USER_INPUT + ALL_THREAD + MAIN_THREAD 모두 호출 (user-turn entry)
    user_input=None → ALL_THREAD + MAIN_THREAD 만 호출 (in-loop, 도구 라운드 후)
    is_subagent=True → MAIN_THREAD 그룹 자동 제외 (원칙 #7)

    각 결과 → Message(role="user", content=(TextBlock(<system-reminder>...),))
    """
    groups = _select_groups(user_input=user_input, is_subagent=ctx.is_subagent)
    targets = _attachments_in(groups, ctx.tool_pool)
    if not targets:
        return []

    # asyncio.wait_for + gather 는 타임아웃 시 모든 task 취소 → 부분 결과 손실
    # 대신 wait() 로 deadline 을 설정하고 완료된 것만 회수
    coros = [_safe_build(att, ctx) for att in targets]
    tasks = [asyncio.create_task(coro) for coro in coros]

    done, pending = await asyncio.wait(
        tasks,
        timeout=COLLECT_TIMEOUT_SECONDS,
        return_when=asyncio.ALL_COMPLETED,
    )

    # pending 태스크들 cancel (cleanup)
    for task in pending:
        task.cancel()

    # 완료된 것만 결과 추출
    results = []
    for task in done:
        try:
            result = task.result()
            if result is not None:
                results.append(result)
        except Exception:
            # 이미 _safe_build 에서 처리됐지만 혹시 모르니 catch
            pass

    return [
        Message(role="user", content=(TextBlock(text=_wrap_system_reminder(r)),))
        for r in results
    ]
