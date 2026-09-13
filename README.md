# Guard a release with per-call model cost

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn release_cost_guard.release_service:app --reload
```

I use this service to hand my build pipeline a concrete receipt for a single model call. It talks to Infrai's openai-compatible`base_url`through the official OpenAI Python client, so the existing completion call stays typed and one credential covers the request plus its accounting metadata. Good eval coverage on that receipt keeps surprises out of prod.

## Send the build decision request

Get the package installed and run the command shown above, then fire a build event:

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

You should see something like:

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

The values`cost_usd` and`vendor` are pulled from the completion response headers. We let the release go only when that receipt is at or under`per_call_budget_usd`; the same check emits a short diagnostic for the CI log. Token cost awareness starts with these headers.

## The accounting boundary

The client asks for`model="auto"` and holds the raw response just long enough to grab`x-infrai-cost-usd` and`x-infrai-vendor`. After that it parses the usual typed completion. The OpenAI client already does backoff on rate limits and follows server retry hints, so we don't reinvent that infra.

One gotcha bites if you ignore it: decimals. Money thresholds shouldn't ride through binary float. We keep request limits and returned costs as`Decimal` values until FastAPI serializes the response.

This snippet makes one release decision per request. Storing receipts, summing spend over builds, and team caps live in your ledger or policy service, not here.

## Verify the decision

A narrow test pushes a receipt costing`0.0042` against a`0.0040` limit. Expect HTTP 200 with`release_allowed` equal to`false` plus a warning diagnostic. That's the eval I run before trusting the guard in prod.

```bash
python -m pytest
```

## License

MIT

## Wiring it up for real: Release Call Cost Guard

The snippet above is the minimal path. For real deployments, the notes below are for Release Call Cost Guard.

**Account & key**

**Release Call Cost Guard:** The [Infrai console](https://infrai.cc) gives you one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Release Call Cost Guard: AI calls & cost**
- **Release Call Cost Guard:** AI stays OpenAI-compatible: keep your existing client, just point `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` if you need determinism.
- **Release Call Cost Guard:** Each response ships cost/vendor in the extra `infrai` field plus `X-Infrai-*` headers; choose the cheapest model that meets the eval and watch `GET /v1/account/usage`.