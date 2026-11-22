"""Keep the development entrypoint on the one port the web app proxies /api/* to."""

from __future__ import annotations

import pytest

from app import main

WINDOWS_LISTING = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:8010         0.0.0.0:0              LISTENING       4321
  TCP    127.0.0.1:8010         127.0.0.1:50572        TIME_WAIT       0
  TCP    127.0.0.1:50572        127.0.0.1:8010         ESTABLISHED     6620
  TCP    [::]:3000              [::]:0                 LISTENING       8388
"""

POSIX_LISTING = """
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID
tcp        0      0 127.0.0.1:8010          0.0.0.0:0               LISTEN      4321
tcp        0      0 127.0.0.1:8010          127.0.0.1:50572         ESTAB       4321
"""


def test_parse_listening_ports_only_counts_listeners() -> None:
    assert main._parse_listening_ports(WINDOWS_LISTING) == {135, 8010, 3000}
    assert main._parse_listening_ports(POSIX_LISTING) == {8010}
    assert main._parse_listening_ports("") == set()


def test_startup_refuses_a_port_that_another_backend_is_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_listening_ports", lambda: {8010})
    with pytest.raises(SystemExit) as stopped:
        main._ensure_port_is_available(8010)
    assert "8010" in str(stopped.value)


def test_startup_accepts_a_port_with_only_time_wait_leftovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_listening_ports", lambda: {135, 3000})
    main._ensure_port_is_available(8010)
