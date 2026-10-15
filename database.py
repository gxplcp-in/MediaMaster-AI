"""
database.py — Supabase (PostgreSQL) ke saath baat karne wala layer.

- supabase-py synchronous hai, isliye har call asyncio.to_thread me chalti hai
  (bot ka event loop block nahi hota).
- Credit/task ka saara logic SQL functions (schema.sql) me hai => atomic.
- Reads (select) fail hone par 2 baar retry hota hai.
- spend_credit par retry NAHI hota (double-deduct se bachne ke liye).
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

import config

log = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Database call fail hone par raise hota hai."""


class Database:
    """Supabase RPC + table access ka chhota wrapper."""

    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()

    # ----- low level --------------------------------------------------------
    def _get_client(self):
        """Supabase client ek baar banao (lazy), baad me reuse karo."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    from supabase import create_client

                    self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        return self._client

    def _rpc_sync(self, fn: str, params: dict) -> Any:
        try:
            return self._get_client().rpc(fn, params).execute().data
        except Exception as exc:  # noqa: BLE001
            raise DatabaseError(f"RPC '{fn}' fail: {exc}") from exc

    def _select_user_sync(self, user_id: int) -> Optional[dict]:
        try:
            res = (
                self._get_client()
                .table("users")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise DatabaseError(f"users select fail: {exc}") from exc
        rows = res.data or []
        return rows[0] if rows else None

    async def _run(self, func, *args, retries: int = 0):
        """Blocking func ko thread me chalao; fail hone par `retries` baar dobara try."""
        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                return await asyncio.to_thread(func, *args)
            except DatabaseError as exc:
                last_exc = exc
                log.warning("DB call fail (attempt %s/%s): %s", attempt + 1, retries + 1, exc)
                if attempt < retries:
                    await asyncio.sleep(0.6 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    # ----- users ------------------------------------------------------------
    async def get_user(self, user_id: int) -> Optional[dict]:
        """User ki poori row (dict) ya None."""
        return await self._run(self._select_user_sync, user_id, retries=2)

    async def upsert_user(
        self, user_id: int, username: Optional[str], first_name: Optional[str], ref: Optional[int]
    ) -> None:
        """Naya user banao / naam update karo. `ref` sirf naye user par lagta hai."""
        await self._run(
            self._rpc_sync,
            "upsert_user",
            {"p_id": user_id, "p_username": username, "p_first": first_name, "p_ref": ref},
            retries=2,
        )

    # ----- tasks ------------------------------------------------------------
    async def arm_task(self, user_id: int, key: str) -> None:
        """Task (yt / sponsor / bonus) khulne ka time save karo."""
        await self._run(self._rpc_sync, "arm_task", {"p_id": user_id, "p_key": key}, retries=1)

    async def complete_task(self, user_id: int, key: str, min_seconds: int) -> str:
        """'yt' / 'sponsor' done mark karo. ok|already|not_started|too_fast|no_user|bad_key"""
        res = await self._run(
            self._rpc_sync,
            "complete_task",
            {"p_id": user_id, "p_key": key, "p_min_seconds": min_seconds},
        )
        return str(res)

    async def finalize_tasks(self, user_id: int, start_credits: int, ref_bonus: int) -> dict:
        """Teeno tasks poore hone par credits do. {'granted': bool, 'referrer': int|None}"""
        res = await self._run(
            self._rpc_sync,
            "finalize_tasks",
            {"p_id": user_id, "p_start_credits": start_credits, "p_ref_bonus": ref_bonus},
        )
        return res if isinstance(res, dict) else {"granted": False, "referrer": None}

    # ----- credits ----------------------------------------------------------
    async def spend_credit(self, user_id: int) -> bool:
        """1 credit kaato. False = credits nahi / tasks pending / banned. (No retry.)"""
        res = await self._run(self._rpc_sync, "spend_credit", {"p_id": user_id})
        return bool(res)

    async def refund_credit(self, user_id: int) -> None:
        """Fail hui analysis ka 1 credit wapas (3 baar tak try)."""
        await self._run(self._rpc_sync, "refund_credit", {"p_id": user_id}, retries=2)

    async def add_credits(self, user_id: int, amount: int) -> Optional[int]:
        """Admin: credits jodo. Naya balance, ya None agar user nahi mila."""
        res = await self._run(self._rpc_sync, "add_credits", {"p_id": user_id, "p_amount": amount})
        return None if res is None else int(res)

    async def claim_bonus(self, user_id: int, min_seconds: int, daily_cap: int, amount: int) -> str:
        """Sponsor bonus. ok|not_started|too_fast|cap_reached|no_access"""
        res = await self._run(
            self._rpc_sync,
            "claim_bonus",
            {
                "p_id": user_id,
                "p_min_seconds": min_seconds,
                "p_daily_cap": daily_cap,
                "p_amount": amount,
            },
        )
        return str(res)

    # ----- stats ------------------------------------------------------------
    async def get_stats(self) -> dict:
        """{'total_users', 'verified_users', 'total_requests'}"""
        res = await self._run(self._rpc_sync, "get_stats", {}, retries=1)
        return res if isinstance(res, dict) else {}


# Poore bot me yahi ek shared instance use hota hai.
db = Database()
