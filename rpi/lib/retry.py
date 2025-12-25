"""Retry utilities with exponential backoff."""
import asyncio
from collections.abc import Awaitable, Callable
from logging import Logger


async def with_retry(
    fn: Callable[[], None] | Callable[[], Awaitable[None]],
    *,
    name: str,
    logger: Logger,
    max_retries: int = 3,
    initial_backoff_sec: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (OSError,),
    run_in_thread: bool = False,
) -> bool:
    """Execute a function with retry logic and exponential backoff.

    Args:
        fn: The function to execute. Can be sync or async.
        name: Name for logging purposes.
        logger: Logger instance to use.
        max_retries: Maximum number of attempts.
        initial_backoff_sec: Initial backoff delay in seconds (doubles each retry).
        retryable_exceptions: Exception types that trigger a retry.
        run_in_thread: If True, run sync fn in a thread pool.

    Returns:
        True if the function succeeded, False otherwise.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            if run_in_thread:
                await asyncio.to_thread(fn)
            elif asyncio.iscoroutinefunction(fn):
                await fn()
            else:
                fn()
            return True
        except retryable_exceptions as e:
            last_error = e
            backoff = initial_backoff_sec * (2**attempt)
            logger.warning(
                "%s attempt %d/%d failed: %s. Retrying in %ds...",
                name,
                attempt + 1,
                max_retries,
                e,
                backoff,
            )
            await asyncio.sleep(backoff)
        except Exception as e:
            logger.error("%s failed (non-retryable): %s", name, e)
            return False

    logger.error(
        "%s failed after %d attempts. Last error: %s",
        name,
        max_retries,
        last_error,
    )
    return False
