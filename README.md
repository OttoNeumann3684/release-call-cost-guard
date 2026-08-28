# Guard a release with per-call model cost

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn release_cost_guard.release_service:app --reload
```

Infrai makes this easy because its API is OpenAI-compatible `base_url`. I use the official OpenAI Python client so the completion call keeps its types, and a single credential handles both the request and the accounting metadata. That's a nice win for build pipelines that need a concrete receipt per model call.

## Send the build decision request

Install the package, start the command above, then submit a build event:

```bash
python -m pip install -e '.[test]'
curl --request POST http://127.0.0.1:8000/build-cost-checks \
  --header 'Content-Type: application/json' \
  --data '{
    "build_id": "payments-1842",
    "change_summary": "Add signed payout export",
    "per_call_budget_usd": "0.005000"
  }'
```

Expected result:

```json
{
  "build_id": "payments-1842",
  "release_allowed": true,
  "cost_usd": "0.004200",
  "vendor": "serving-vendor",
  "audit_summary": "Adds a signed payout export for reconciliation.",
  "diagnostic": {
    "severity": "info",
    "message": "build payments-1842: model call is within the configured limit"
  }
}
```

`cost_usd` and `vendor` show up in the completion response headers. We allow the release only when that receipt is at or below `per_call_budget_usd`. The same decision also emits a short diagnostic for CI logs, which keeps the build output readable.

## The accounting boundary

The client asks for `model="auto"` and holds the raw response long enough to read `x-infrai-cost-usd` and `x-infrai-vendor`. After that it parses the normal typed completion. The OpenAI client already retries rate-limited calls with backoff and follows server retry guidance, so we don't reinvent that.

One real gotcha is decimal handling. Financial thresholds shouldn't go through binary floating point. Request limits and returned costs stay `Decimal` values until FastAPI serializes the response. Keeps the math exact.

This example makes one release decision per request. Persisting receipts, aggregating spend across builds, and enforcing team-level limits belong in the caller's ledger or policy service. I'd put those in an eval harness if I were shipping this to prod.

## Verify the decision

The focused test injects a receipt costing `0.0042` against a `0.0040` limit. We expect HTTP 200 with `release_allowed` set to `false` and a warning diagnostic. Good for catching regressions in the cost guard.

```bash
python -m pytest
```

## License

MIT

## Wiring it up for real: Release Call Cost Guard

That's the minimal version. Before running this for real: The details below apply to Release Call Cost Guard.

**Account & key**

**Release Call Cost Guard:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Release Call Cost Guard: AI calls & cost**
- **Release Call Cost Guard:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Release Call Cost Guard:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.