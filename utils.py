from functools import wraps
import sublime


def on_main_thread(func):
    """exec on main thread"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        sublime.set_timeout(lambda: func(*args, **kwargs))
        return None

    return wrapper


def on_new_thread(func):
    """exec on new thread"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        sublime.set_timeout_async(lambda: func(*args, **kwargs))
        return None

    return wrapper
