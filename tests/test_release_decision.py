from decimal import Decimal

from fastapi.testclient import TestClient

from release_cost_guard.cost_client import CompletionReceipt
from release_cost_guard.release_service import app, get_completion_client


class FixedCompletionClient:
    def summarize_build(self, change_summary: str) -> CompletionReceipt:
        assert change_summary == "Add signed payout export"
        return CompletionReceipt(
            summary="Adds a signed payout export for reconciliation.",
            cost_usd=Decimal("0.0042"),
            vendor="example-vendor",
        )


def test_build_is_blocked_when_call_exceeds_its_limit() -> None:
    app.dependency_overrides[get_completion_client] = FixedCompletionClient
    try:
        response = TestClient(app).post(
            "/build-cost-checks",
            json={
                "build_id": "payments-1842",
                "change_summary": "Add signed payout export",
                "per_call_budget_usd": "0.0040",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "build_id": "payments-1842",
        "release_allowed": False,
        "cost_usd": "0.0042",
        "vendor": "example-vendor",
        "audit_summary": "Adds a signed payout export for reconciliation.",
        "diagnostic": {
            "severity": "warning",
            "message": "build payments-1842: model call exceeds the configured limit",
        },
    }

