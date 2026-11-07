import os

import pytest

os.environ["PERMIT_AI_OFFLINE"] = "1"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import store
    from app.main import app

    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c
