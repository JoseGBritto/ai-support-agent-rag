import pytest

from supportbot.server import create_app


@pytest.fixture
def client(settings, make_agent):
    settings.rate_limit_per_minute = 5
    app = create_app(settings, make_agent())
    return app.test_client()


def test_chat_answers_and_returns_conversation_id(client):
    r = client.post("/api/chat", json={"message": "How long does shipping to Chile take?"})
    data = r.get_json()
    assert r.status_code == 200 and data["conversation_id"] and "5 to 8" in data["answer"]


def test_chat_validates_input(client):
    assert client.post("/api/chat", json={}).status_code == 400
    assert client.post("/api/chat", json={"message": "x" * 1001}).status_code == 400


def test_rate_limit(client):
    codes = [client.post("/api/chat", json={"message": "shipping"}).status_code for _ in range(6)]
    assert codes[-1] == 429


def test_handoff_email_flow(client):
    conv = client.post("/api/chat", json={"message": "Do you have a store in Paris with live music?"}).get_json()
    assert conv["handoff"] is True
    assert client.post("/api/handoff", json={"conversation_id": conv["conversation_id"], "email": "bad"}).status_code == 400
    ok = client.post("/api/handoff", json={"conversation_id": conv["conversation_id"], "email": "ana@example.com"})
    assert ok.get_json() == {"ok": True}


def test_admin_endpoints_require_token(client):
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/api/admin/stats", headers={"Authorization": "Bearer wrong"}).status_code == 401
    client.post("/api/chat", json={"message": "Do you have a store in Paris with live music?"})
    auth = {"Authorization": "Bearer secret"}
    stats = client.get("/api/admin/stats", headers=auth).get_json()
    assert stats["questions"] == 1 and stats["handoffs"] == 1 and stats["chunks"] > 10
    assert client.get("/api/admin/gaps", headers=auth).get_json()["gaps"][0]["times"] == 1
    assert client.post("/api/admin/reindex", headers=auth).get_json()["chunks"] == stats["chunks"]


def test_widget_demo_and_cors(client):
    w = client.get("/widget.js")
    assert w.status_code == 200 and "attachShadow" in w.get_data(as_text=True)
    assert "widget.js" in client.get("/").get_data(as_text=True)
    r = client.post("/api/chat", json={"message": "shipping"}, headers={"Origin": "https://shop.example"})
    assert r.headers["Access-Control-Allow-Origin"] == "https://shop.example"


def test_placeholder_admin_token_keeps_admin_locked(settings, make_agent):
    settings.admin_token = "change-me"
    client = create_app(settings, make_agent()).test_client()
    assert client.get("/api/admin/stats", headers={"Authorization": "Bearer change-me"}).status_code == 401


def test_rate_limit_is_per_visitor_behind_a_proxy(settings, make_agent):
    settings.rate_limit_per_minute, settings.trusted_proxy_hops = 2, 1
    client = create_app(settings, make_agent()).test_client()
    send = lambda ip: client.post("/api/chat", json={"message": "shipping"}, headers={"X-Forwarded-For": ip}).status_code
    assert [send("1.1.1.1"), send("1.1.1.1"), send("1.1.1.1")] == [200, 200, 429]
    assert send("2.2.2.2") == 200  # another visitor is not blocked
