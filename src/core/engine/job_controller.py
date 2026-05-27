import asyncio
import time
from dataclasses import dataclass, field
from src.config.settings import USER_COOLDOWN_SECONDS, INSTAGRAM_USER_COOLDOWN_SECONDS

@dataclass
class _UserJobState:
    task: asyncio.Task | None = None
    busy: bool = False
    cooldown_until: float = 0.0
    instagram_cooldown_until: float = 0.0
    pending_url: str | None = None
    last_download_time: float = 0.0
    waiting_message_id: int | None = None
    duplicate_message_ids: list[int] = field(default_factory=list)

class UserJobController:
    def __init__(self):
        self._states: dict[int, _UserJobState] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: int) -> tuple[bool, int]:
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())

            if state.busy:
                return False, -1

            now = time.monotonic()
            if now < state.cooldown_until:
                remaining = int(state.cooldown_until - now)
                if state.cooldown_until - now > remaining:
                    remaining += 1
                return False, max(1, remaining)

            state.busy = True
            state.task = None
            return True, 0

    async def start_task(self, user_id: int, coro):
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.task = asyncio.create_task(self._runner(user_id, coro))

    async def release(self, user_id: int):
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.busy = False
            state.task = None
            state.cooldown_until = time.monotonic() + USER_COOLDOWN_SECONDS

    async def set_pending_url(self, user_id: int, url: str):
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.pending_url = url

    async def get_pending_url(self, user_id: int) -> str | None:
        async with self._lock:
            return self._states.get(user_id, _UserJobState()).pending_url

    async def _runner(self, user_id: int, coro):
        try:
            await coro
        except asyncio.CancelledError:
            raise
        finally:
            async with self._lock:
                state = self._states.setdefault(user_id, _UserJobState())
                state.busy = False
                state.task = None
                state.cooldown_until = time.monotonic() + USER_COOLDOWN_SECONDS

    async def wait_for_download_cooldown(self, user_id: int) -> None:
        """Wait for the 5-second download cooldown before allowing the next request."""
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            now = time.monotonic()
            time_since_last_download = now - state.last_download_time
            
            if time_since_last_download < 5.0:
                wait_time = 5.0 - time_since_last_download
            else:
                wait_time = 0.0
        
        # Release lock before sleeping
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        # Update last download time
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.last_download_time = time.monotonic()

    async def acquire_instagram_request(self, user_id: int) -> tuple[bool, int]:
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            now = time.monotonic()

            if now < state.instagram_cooldown_until:
                remaining = int(state.instagram_cooldown_until - now)
                if state.instagram_cooldown_until - now > remaining:
                    remaining += 1
                return False, max(1, remaining)

            state.instagram_cooldown_until = now + INSTAGRAM_USER_COOLDOWN_SECONDS
            return True, 0

    async def set_waiting_message(self, user_id: int, message_id: int):
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.waiting_message_id = message_id

    async def add_duplicate_message(self, user_id: int, message_id: int):
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.duplicate_message_ids.append(message_id)

    async def get_temporary_messages(self, user_id: int) -> tuple[int | None, list[int]]:
        """Get all temporary messages (waiting + duplicates) for cleanup."""
        async with self._lock:
            state = self._states.get(user_id, _UserJobState())
            return state.waiting_message_id, state.duplicate_message_ids.copy()

    async def clear_temporary_messages(self, user_id: int):
        """Clear all temporary message tracking after they're deleted."""
        async with self._lock:
            state = self._states.setdefault(user_id, _UserJobState())
            state.waiting_message_id = None
            state.duplicate_message_ids = []

job_controller = UserJobController()
