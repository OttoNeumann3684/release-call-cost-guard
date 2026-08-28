from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError
from pydantic import BaseModel, Field

from .cost_client import CompletionReceipt, CostMetadataError, InfraiCompletionClient


class BuildCostRequest(BaseModel):
    build_id: str = Field(min_length=1, max_length=100)
    change_summary: str = Field(min_length=1, max_length=4000)
    per_call_budget_usd: Decimal = Field(gt=0, max_digits=12, decimal_places=6)


class DeveloperDiagnostic(BaseModel):
    severity: str
    message: str


class BuildCostDecision(BaseModel):
    build_id: str
    release_allowed: bool
    cost_usd: Decimal
    vendor: str
    audit_summary: str
    diagnostic: DeveloperDiagnostic


def decide_release(request: BuildCostRequest, receipt: CompletionReceipt) -> BuildCostDecision:
    release_allowed = receipt.cost_usd <= request.per_call_budget_usd
    if release_allowed:
        diagnostic = DeveloperDiagnostic(
            severity="info",
            message=f"build {request.build_id}: model call is within the configured limit",
        )
    else:
        diagnostic = DeveloperDiagnostic(
            severity="warning",
            message=f"build {request.build_id}: model call exceeds the configured limit",
        )
    return BuildCostDecision(
        build_id=request.build_id,
        release_allowed=release_allowed,
        cost_usd=receipt.cost_usd,
        vendor=receipt.vendor,
        audit_summary=receipt.summary,
        diagnostic=diagnostic,
    )


def get_completion_client() -> InfraiCompletionClient:
    return InfraiCompletionClient()


app = FastAPI(title="Release cost guard")


@app.post("/build-cost-checks", response_model=BuildCostDecision)
def check_build_cost(
    request: BuildCostRequest,
    client: Annotated[InfraiCompletionClient, Depends(get_completion_client)],
) -> BuildCostDecision:
    try:
        receipt = client.summarize_build(request.change_summary)
    except APIStatusError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail="Model request was rejected") from exc
    except (APIConnectionError, CostMetadataError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return decide_release(request, receipt)
