"""
Retry utilities for handling transient API failures.

Provides decorators and utilities for retrying failed API calls with
exponential backoff, particularly useful for rate-limited or flaky APIs.
"""

import time
import asyncio
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional, Any, TypeVar
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def with_timeout(
    coro,
    timeout_seconds: float,
    operation_name: str = "operation",
    default_on_timeout: Any = None,
) -> Any:
    """
    Wrap an async coroutine with a timeout.
    
    Args:
        coro: The coroutine to execute
        timeout_seconds: Maximum seconds to wait
        operation_name: Name for logging purposes
        default_on_timeout: Value to return if timeout occurs (if None, raises TimeoutError)
    
    Returns:
        The coroutine result, or default_on_timeout if timeout and default provided
        
    Raises:
        asyncio.TimeoutError: If timeout occurs and default_on_timeout is None
    
    Example:
        ```python
        result = await with_timeout(
            fetch_data_async(),
            timeout_seconds=30,
            operation_name="fetch_data",
            default_on_timeout=[]
        )
        ```
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"{operation_name} timed out after {timeout_seconds}s")
        if default_on_timeout is not None:
            return default_on_timeout
        raise


def sync_tool_with_timeout(
    timeout_seconds: float = 60.0,
    default_on_timeout: Any = None,
):
    """
    Decorator that wraps a synchronous tool call and enforces a timeout.
    
    Uses threading to enforce timeout on sync functions. For deep research tools
    that make external API calls, this prevents any single tool from hanging
    the entire workflow.
    
    Args:
        timeout_seconds: Maximum seconds to wait (default: 60)
        default_on_timeout: Value to return on timeout (default: None)
    
    Example:
        ```python
        @sync_tool_with_timeout(timeout_seconds=30, default_on_timeout="")
        def get_company_news(ticker: str) -> str:
            return external_api.fetch_news(ticker)
        ```
    """
    import concurrent.futures
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"{func.__name__} timed out after {timeout_seconds}s")
                    # Record timeout in metrics
                    tool_metrics.record_failure(func.__name__, f"Timeout after {timeout_seconds}s")
                    if default_on_timeout is not None:
                        return default_on_timeout
                    raise TimeoutError(f"{func.__name__} timed out after {timeout_seconds}s")
        
        return wrapper
    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_failure: Optional[Callable[[Exception, int], Any]] = None,
    jitter: bool = True
):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)
        on_failure: Optional callback function called on each failure with (exception, attempt_number)
        jitter: Add random jitter to delay to prevent thundering herd (default: True)
    
    Returns:
        Decorated function that retries on failure
    
    Example:
        ```python
        @retry_with_backoff(max_retries=3, initial_delay=2.0)
        def fetch_data():
            response = requests.get("https://api.example.com/data")
            response.raise_for_status()
            return response.json()
        ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt == max_retries:
                        logger.warning(
                            f"{func.__name__} failed after {max_retries} retries: {str(e)}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.info(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Call failure callback if provided
                    if on_failure:
                        on_failure(e, attempt + 1)
                    
                    time.sleep(delay)
            
            # All retries exhausted, raise the last exception
            raise last_exception
        
        return wrapper
    return decorator


def retry_on_rate_limit(
    max_retries: int = 3,
    initial_delay: float = 2.0,
    status_codes: Tuple[int, ...] = (429, 503)
):
    """
    Decorator specifically for retrying on rate limit errors (HTTP 429/503).
    
    This is a convenience wrapper around retry_with_backoff configured
    for common rate limiting scenarios.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 2.0)
        status_codes: HTTP status codes to retry on (default: 429, 503)
    
    Returns:
        Decorated function that retries on rate limit
    
    Example:
        ```python
        @retry_on_rate_limit(max_retries=5, initial_delay=3.0)
        def fetch_google_trends(keyword: str):
            response = requests.get(f"https://trends.google.com/api?q={keyword}")
            if response.status_code in (429, 503):
                raise RateLimitError(f"Rate limited: {response.status_code}")
            return response.json()
        ```
    """
    from requests.exceptions import HTTPError
    
    def should_retry(exception: Exception) -> bool:
        """Check if exception is a rate limit error"""
        if isinstance(exception, HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                return exception.response.status_code in status_codes
        # Also catch generic rate limit exceptions
        if 'rate limit' in str(exception).lower():
            return True
        if any(str(code) in str(exception) for code in status_codes):
            return True
        return False
    
    # Define custom exception filter
    class RateLimitException(Exception):
        pass
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            @retry_with_backoff(
                max_retries=max_retries,
                initial_delay=initial_delay,
                exponential_base=2.0,
                max_delay=30.0,
                exceptions=(Exception,),  # Catch all, filter in should_retry
                jitter=True
            )
            def inner():
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if should_retry(e):
                        # Convert to our custom exception for retry logic
                        raise RateLimitException(str(e)) from e
                    # Don't retry on other exceptions
                    raise
            
            try:
                return inner()
            except RateLimitException as e:
                # Convert back to original exception
                if e.__cause__:
                    raise e.__cause__
                raise
        
        return wrapper
    return decorator


def skip_on_failure(
    default_return: Any = None,
    log_level: str = "warning"
):
    """
    Decorator that catches exceptions and returns a default value instead of failing.
    
    Useful for non-critical tools where failure shouldn't block the workflow.
    
    Args:
        default_return: Value to return on failure (default: None)
        log_level: Logging level for failures ("debug", "info", "warning", "error")
    
    Returns:
        Decorated function that returns default_return on failure
    
    Example:
        ```python
        @skip_on_failure(default_return=[], log_level="warning")
        def get_optional_data():
            # If this fails, return [] instead of raising
            return fetch_from_flaky_api()
        ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level.lower(), logger.warning)
                log_func(
                    f"{func.__name__} failed (skipping): {type(e).__name__}: {str(e)}"
                )
                return default_return
        
        return wrapper
    return decorator


class ToolMetrics:
    """
    Simple in-memory metrics collector for tool performance monitoring.
    
    Tracks success/failure rates, latency, and error types per tool.
    """
    
    def __init__(self):
        self._metrics = {}
    
    def record_success(self, tool_name: str, duration: float):
        """Record a successful tool execution"""
        if tool_name not in self._metrics:
            self._metrics[tool_name] = {
                "success_count": 0,
                "failure_count": 0,
                "total_duration": 0.0,
                "errors": []
            }
        
        self._metrics[tool_name]["success_count"] += 1
        self._metrics[tool_name]["total_duration"] += duration
    
    def record_failure(self, tool_name: str, error: str, duration: float = 0.0):
        """Record a failed tool execution"""
        if tool_name not in self._metrics:
            self._metrics[tool_name] = {
                "success_count": 0,
                "failure_count": 0,
                "total_duration": 0.0,
                "errors": []
            }
        
        self._metrics[tool_name]["failure_count"] += 1
        self._metrics[tool_name]["total_duration"] += duration
        
        # Keep last 10 errors
        self._metrics[tool_name]["errors"].append(error)
        if len(self._metrics[tool_name]["errors"]) > 10:
            self._metrics[tool_name]["errors"].pop(0)
    
    def get_stats(self) -> dict:
        """Get statistics for all tools"""
        stats = {}
        for tool_name, metrics in self._metrics.items():
            total_calls = metrics["success_count"] + metrics["failure_count"]
            success_rate = metrics["success_count"] / total_calls if total_calls > 0 else 0
            avg_duration = metrics["total_duration"] / total_calls if total_calls > 0 else 0
            
            stats[tool_name] = {
                "total_calls": total_calls,
                "success_count": metrics["success_count"],
                "failure_count": metrics["failure_count"],
                "success_rate": round(success_rate * 100, 2),
                "avg_duration_seconds": round(avg_duration, 2),
                "recent_errors": metrics["errors"][-5:],  # Last 5 errors
            }
        
        return stats
    
    def reset(self):
        """Clear all metrics"""
        self._metrics.clear()


# Global metrics instance
tool_metrics = ToolMetrics()
