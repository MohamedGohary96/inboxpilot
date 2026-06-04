"""Lightweight in-process poll progress tracker.

Updated from poll_inbox / poll_slack (background threads) and read by the
/api/poll/progress endpoint (main thread). A plain dict is safe here because
Python's GIL ensures dict reads and writes are atomic at the bytecode level,
and we only ever have one poll running at a time.
"""
import threading

_state: dict = {
    "phase": "idle",
    "current": 0,
    "total": 0,
    "done": True,
}

_lock = threading.Lock()


def try_acquire() -> bool:
    """Returns True if no poll is running and the lock was acquired."""
    return _lock.acquire(blocking=False)


def release() -> None:
    try:
        _lock.release()
    except RuntimeError:
        pass


def reset() -> None:
    _state.update(phase="Starting…", current=0, total=0, done=False)


def update(phase: str, current: int = 0, total: int = 0) -> None:
    _state.update(phase=phase, current=current, total=total)


def complete() -> None:
    _state.update(phase="Done", current=0, total=0, done=True)


def get() -> dict:
    return dict(_state)
