"""Integration tests for Vite/React SPA Static Hosting and Fallback Routing (Issue #019 / DoD-F1)."""

import pytest
from fastapi.testclient import TestClient

from src.presentation.api.main import create_app, resolve_static_dir


@pytest.fixture
def spa_client() -> TestClient:
    """TestClient using the real frontend/dist directory if built."""
    app = create_app()
    return TestClient(app)


# --- Scenario 1 & 3: SPA Root and Route Fallback ---
def test_spa_root_and_client_routes(spa_client: TestClient):
    """シナリオ 1 & 3: ルートパスおよび SPA クライアントサイドルートでの index.html 配信"""
    routes_to_test = [
        "/",
        "/practice",
        "/questions",
        "/chat",
        "/insights",
        "/analytics",
        "/unknown-path",  # シナリオ 6: 未定義ルートも index.html を返し React 側で 404 処理
    ]

    for route in routes_to_test:
        res = spa_client.get(route)
        assert res.status_code == 200, f"Route {route} failed with status {res.status_code}"
        content_type = res.headers.get("content-type", "")
        assert "text/html" in content_type
        assert '<div id="root">' in res.text
        assert "IPA Exam RAG" in res.text
        assert "no-cache" in res.headers.get("cache-control", "")


# --- Scenario 5: PWA Manifest & Service Worker ---
def test_pwa_manifest_and_static_files(spa_client: TestClient):
    """シナリオ 5: PWA マニフェストおよび Service Worker、SVG アイコンの直接配信"""
    # 1. Manifest
    res_manifest = spa_client.get("/manifest.webmanifest")
    assert res_manifest.status_code == 200
    assert "no-cache" in res_manifest.headers.get("cache-control", "")
    manifest_data = res_manifest.json()
    assert manifest_data["short_name"] == "IPA道場"
    assert manifest_data["display"] == "standalone"
    assert manifest_data["theme_color"] == "#0B0F19"

    # 2. Service Worker
    res_sw = spa_client.get("/sw.js")
    assert res_sw.status_code == 200
    assert "no-cache" in res_sw.headers.get("cache-control", "")
    assert "CACHE_NAME" in res_sw.text
    assert "addEventListener('fetch'" in res_sw.text

    # 3. Icon SVG
    res_icon = spa_client.get("/icon.svg")
    assert res_icon.status_code == 200
    assert "<svg" in res_icon.text


# --- Asset Files Delivery ---
def test_static_asset_bundles_delivery(spa_client: TestClient):
    """ビルド成果物 (CSS / JS) が /assets/* 経由で正常に配信されることを検証"""
    dist_dir = resolve_static_dir()
    assets_dir = dist_dir / "assets"
    if assets_dir.exists() and assets_dir.is_dir():
        asset_files = [f for f in assets_dir.iterdir() if f.is_file()]
        assert len(asset_files) > 0, "Built assets directory should not be empty"

        sample_asset = asset_files[0]
        res = spa_client.get(f"/assets/{sample_asset.name}")
        assert res.status_code == 200
        assert len(res.content) > 0


# --- Scenario 8: API Boundary Exception ---
def test_api_boundary_not_swallowed_by_spa_fallback(spa_client: TestClient):
    """シナリオ 8: 存在しない API パス (/api/*) が SPA Fallback に呑まれず必ず 404 JSON を返すこと"""
    res = spa_client.get("/api/nonexistent-endpoint")
    assert res.status_code == 404
    assert res.headers.get("content-type") == "application/json"
    data = res.json()
    assert "detail" in data
    assert "API endpoint not found: /api/nonexistent-endpoint" in data["detail"]
