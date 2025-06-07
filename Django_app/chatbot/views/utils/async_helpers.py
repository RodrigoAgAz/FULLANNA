from asgiref.sync import sync_to_async
import inspect
import logging

logger = logging.getLogger(__name__)

async def ensure_async(func, *args, **kwargs):
    """
    Ensures a function is called asynchronously.
    If it's already async, await it. If sync, wrap with sync_to_async.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        async_func = sync_to_async(func)
        return await async_func(*args, **kwargs)

async def safe_await(obj):
    """
    Safely await an object if it's a coroutine, otherwise return it.
    """
    if inspect.iscoroutine(obj):
        logger.warning(f"Found unawaited coroutine: {obj}")
        return await obj
    return obj