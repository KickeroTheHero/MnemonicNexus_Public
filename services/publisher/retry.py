"""Publisher retry logic and dead letter queue handling."""

import random
from datetime import datetime, timedelta
from typing import Any, Dict

import asyncpg


class RetryHandler:
    """Sophisticated retry logic with exponential backoff."""

    MAX_RETRIES = 10
    BASE_DELAY_SECONDS = 1
    MAX_DELAY_SECONDS = 3600  # 1 hour

    @classmethod
    def calculate_next_retry(cls, attempt: int) -> datetime:
        """Calculate next retry time with exponential backoff + jitter."""
        delay = min(
            cls.BASE_DELAY_SECONDS * (2**attempt),
            cls.MAX_DELAY_SECONDS,
        )

        # Add jitter to prevent thundering herd
        jitter = delay * 0.1 * random.random()
        final_delay = delay + jitter

        return datetime.utcnow() + timedelta(seconds=final_delay)

    @classmethod
    def should_move_to_dlq(cls, attempt: int) -> bool:
        """Determine if event should move to dead letter queue."""
        return attempt >= cls.MAX_RETRIES


class DeadLetterQueue:
    """Dead letter queue for poison messages."""

    def __init__(self, publisher_id: str = "cdc-publisher-v2") -> None:
        self.publisher_id = publisher_id

    async def move_to_dlq(
        self,
        conn: asyncpg.Connection,
        event: Dict[str, Any],
        error: str,
    ) -> None:
        """Move failed event to DLQ for manual investigation."""
        # Prefer server-side function which also deletes from outbox
        await conn.execute(
            "SELECT event_core.move_to_dlq($1, $2, $3)",
            event["global_seq"],
            error,
            self.publisher_id,
        )
