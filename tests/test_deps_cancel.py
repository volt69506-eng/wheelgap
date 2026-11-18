"""Regression test for #514: Ctrl-C must not wait on in-flight prefetch lookups.

`fill_all` drives its lookups through a thread pool. Plain
`concurrent.futures.ThreadPoolExecutor` workers are not daemons, so after
Ctrl-C the interpreter waits at exit for every fetch still in flight. On a
stalled network each fetch can take about 20 s x 4 attempts plus backoff, and
there can be up to 16 of them.

The property that matters is that the pool's threads are daemons, so the
process can leave while a fetch is still blocked.
"""

import threading
import time

from wheelgap import pypi


def _slow_fill(monkeypatch):
    """Patch fill so a lookup blocks until the test releases it."""
    started = threading.Event()

    def slow_fill(package, **kwargs):
        started.set()
        time.sleep(30)  # a stalled network never returns

    monkeypatch.setattr(pypi, "fill", slow_fill)
    monkeypatch.setattr(pypi, "may_look_up", lambda registry, simple: True)
    return started


def _package():
    return [pypi.Package(name="a", version="1.0")]


def test_the_worker_pool_creates_daemon_threads(monkeypatch):
    """The pool fill_all uses must build daemon threads."""
    started = _slow_fill(monkeypatch)

    thread = threading.Thread(target=pypi.fill_all, kwargs={"packages": _package(), "workers": 1})
    thread.start()
    assert started.wait(timeout=5), "the lookup never started"

    pool_threads = [t for t in threading.enumerate() if t.name.startswith("wheelgap")]
    assert pool_threads, "no worker thread was created"
    assert all(t.daemon for t in pool_threads), "a pool thread is not a daemon"


def test_daemon_pool_threads_are_daemons():
    """The pool itself must build daemon threads."""
    pool = pypi.DaemonThreadPool(max_workers=1)
    pool.submit(lambda: time.sleep(30))
    pool_threads = [t for t in threading.enumerate() if t.name.startswith("wheelgap")]
    assert pool_threads
    assert all(t.daemon for t in pool_threads)
    pool.shutdown(wait=False)
