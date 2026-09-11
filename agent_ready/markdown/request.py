from contextlib import contextmanager
from contextvars import ContextVar


_request = ContextVar("agent_ready_request", default=None)


def current_request():
    return _request.get()


@contextmanager
def use_request(request):
    token = _request.set(request)
    try:
        yield
    finally:
        _request.reset(token)
