from functools import wraps
import sublime
import traceback


def on_main_thread(func):
    """Execute function on Sublime's main thread."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        def run():
            try:
                return func(*args, **kwargs)
            except Exception:
                traceback.print_exc()

        sublime.set_timeout(run, 0)
        return None  # fire-and-forget

    return wrapper


def on_new_thread(func):
    """Execute function asynchronously on Sublime's worker thread."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        def run():
            try:
                return func(*args, **kwargs)
            except Exception:
                traceback.print_exc()

        sublime.set_timeout_async(run, 0)
        return None  # fire-and-forget

    return wrapper
