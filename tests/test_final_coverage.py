
"""Additional backend and deployment lifecycle tests."""

import subprocess
from unittest.mock import Mock

from fastapi.testclient import TestClient


def test_foundation_health():
    from backend.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "phase": "foundation",
        "model_ready": False,
    }


def test_foundation_datasets(monkeypatch):
    from backend.main import app
    from backend.api import system

    sample = [
        {
            "name": "synthetic.csv",
            "role": "primary",
            "rows": 10,
            "columns": 8,
            "status": "verified",
        }
    ]

    inventory = Mock(return_value=sample)
    monkeypatch.setattr(system, "dataset_status", inventory)

    with TestClient(app) as client:
        response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    assert response.json() == {"datasets": sample}
    inventory.assert_called_once_with()


def test_supervisor_child_failure(monkeypatch):
    from backend import phase9_supervisor as supervisor

    api = Mock()
    gateway = Mock()

    api.poll.return_value = 1
    gateway.poll.return_value = None

    gateway.wait.side_effect = [
        subprocess.TimeoutExpired("gateway", 8),
        0,
    ]

    popen = Mock(side_effect=[api, gateway])

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    monkeypatch.setattr(supervisor.signal, "signal", Mock())

    assert supervisor.main() == 1
    assert popen.call_count == 2

    assert popen.call_args_list[0].args[0][-1] == "api"
    assert popen.call_args_list[1].args[0][-1] == "gateway"

    api.terminate.assert_not_called()
    gateway.terminate.assert_called_once()
    gateway.kill.assert_called_once()
    assert gateway.wait.call_count == 2


def test_supervisor_graceful_shutdown(monkeypatch):
    from backend import phase9_supervisor as supervisor

    api = Mock()
    gateway = Mock()

    api.poll.return_value = None
    gateway.poll.return_value = None

    popen = Mock(side_effect=[api, gateway])
    signal_handler = Mock()

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    monkeypatch.setattr(supervisor.signal, "signal", signal_handler)

    def simulate_shutdown(seconds):
        handler = signal_handler.call_args.args[1]
        handler(supervisor.signal.SIGTERM, None)

    monkeypatch.setattr(supervisor.time, "sleep", simulate_shutdown)

    assert supervisor.main() == 0

    for child in (api, gateway):
        child.terminate.assert_called_once()
        child.wait.assert_called_once_with(timeout=8)
        child.kill.assert_not_called()
