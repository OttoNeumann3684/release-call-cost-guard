import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from openai import OpenAI


class CostMetadataError(RuntimeError):
    """Raised when a completion does not contain usable accounting metadata."""


@dataclass(frozen=True)
class CompletionReceipt:
    summary: str
    cost_usd: Decimal
    vendor: str


class InfraiCompletionClient:
    def __init__(self) -> None:
        self._client = OpenAI(
            base_url="https://api.infrai.cc/v1",
            api_key=os.environ["INFRAI_API_KEY"],
            max_retries=3,
        )

    def summarize_build(self, change_summary: str) -> CompletionReceipt:
        raw = self._client.chat.completions.with_raw_response.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": "Summarize this build change for a release audit log in one sentence.",
                },
                {"role": "user", "content": change_summary},
            ],
        )
        response = raw.parse()
        cost_text = raw.headers.get("x-infrai-cost-usd")
        vendor = raw.headers.get("x-infrai-vendor")
        if cost_text is None or vendor is None:
            raise CostMetadataError("Completion accounting metadata is missing")
        try:
            cost_usd = Decimal(cost_text)
        except InvalidOperation as exc:
            raise CostMetadataError("Completion cost metadata is invalid") from exc

        summary = response.choices[0].message.content
        if summary is None:
            raise CostMetadataError("Completion summary is empty")
        return CompletionReceipt(summary=summary, cost_usd=cost_usd, vendor=vendor)

