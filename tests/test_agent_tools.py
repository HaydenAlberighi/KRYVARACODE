import uuid


def _name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_agent_tools_require_auth(client):
    r = client.get("/api/v1/agent/tools")
    assert r.status_code == 401


def test_agent_tools_list_openai_shape(client, auth_headers):
    r = client.get("/api/v1/agent/tools", headers=auth_headers)
    assert r.status_code == 200
    tools = r.json()
    assert len(tools) == 28
    by_name = {t["name"]: t for t in tools}
    for expected in (
        "system_info",
        "list_datasets",
        "get_dataset",
        "create_dataset",
        "list_models",
        "register_model",
        "list_experiments",
        "predict",
        "train_model",
    ):
        assert expected in by_name
    sample = by_name["list_datasets"]
    assert sample.get("description")
    params = sample["parameters"]
    assert params["type"] == "object"
    assert "skip" in params["properties"]
    assert "limit" in params["properties"]


def test_agent_invoke_requires_auth(client):
    r = client.post("/api/v1/agent/tools/list_datasets/invoke", json={"arguments": {}})
    assert r.status_code == 401


def test_agent_invoke_list_datasets(client, auth_headers):
    r = client.post(
        "/api/v1/agent/tools/list_datasets/invoke",
        json={"arguments": {}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "total" in body


def test_agent_invoke_unknown_tool_404(client, auth_headers):
    r = client.post(
        "/api/v1/agent/tools/nope/invoke",
        json={"arguments": {}},
        headers=auth_headers,
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "not_found"


def test_agent_invoke_bad_args_422(client, auth_headers):
    r = client.post(
        "/api/v1/agent/tools/create_dataset/invoke",
        json={"arguments": {}},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_agent_invoke_system_info(client, auth_headers):
    r = client.post(
        "/api/v1/agent/tools/system_info/invoke",
        json={"arguments": {}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert "KRYVARACODE" in str(r.json())


def test_agent_invoke_predict_without_model_503(client, auth_headers):
    r = client.post(
        "/api/v1/agent/tools/predict/invoke",
        json={"arguments": {"features": {"feature1": 0.5, "feature2": 1.0}}},
        headers=auth_headers,
    )
    assert r.status_code == 503
