# ResolveAI

ResolveAI is a customer-support resolution copilot built with a production-minded
backend structure. It will eventually combine policy retrieval, customer and
order tools, deterministic business rules, LangGraph orchestration, human
approval, and evaluation.

## Current milestone

The current version contains the backend foundation, domain contracts, SQLite persistence, basic support APIs, a deterministic policy knowledge base, deterministic order rules, and a resolution-preview workflow:

- FastAPI application
- Environment-based configuration
- Health endpoint
- Versioned API endpoint
- Validated customer, product, order, ticket, proposal, and audit models
- Pydantic request and response schemas
- SQLAlchemy rows, repositories, SQLite sessions, and deterministic demo seed data
- Customer, order, and support-ticket lookup/create APIs with ownership checks
- Markdown policy loading, bounded chunks, keyword retrieval, and source citations
- Deterministic cancellation, refund, return, replacement, and delivery-date rules
- Database-backed resolution previews combining order rules with policy citations
- Automated model and endpoint tests

## Project structure

```text
resolve-ai/
├── app/
│   ├── core/
│   │   └── config.py
│   ├── models/
│   │   └── domain.py
│   ├── schemas/
│   │   ├── domain.py
│   │   ├── policy.py
│   │   └── workflow.py
│   ├── db/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── seed.py
│   │   └── session.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routers/
│   │       ├── policies.py
│   │       ├── support.py
│   │       └── workflow.py
│   └── main.py
├── policies/
│   ├── cancellation.md
│   ├── replacements.md
│   └── returns.md
├── tests/
│   ├── test_api.py
│   ├── test_db.py
│   ├── test_domain_models.py
│   ├── test_health.py
│   ├── test_policy_api.py
│   ├── test_policy_kb.py
│   ├── test_resolution_workflow.py
│   └── test_workflow_api.py
├── .env.example
├── pyproject.toml
└── README.md
```

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m uvicorn app.main:app --reload
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

Run tests with:

```bash
python -m pytest
```

## Local database

The default database is `resolve_ai.sqlite3` in the project root. Create tables
and deterministic demo data with:

```bash
python -m app.db.seed
```

Run the seed command again safely; fixed demo records are not duplicated.

## Support API

With demo data seeded, these endpoints are available:

```text
GET  /api/v1/customers/{customer_id}
GET  /api/v1/customers/{customer_id}/orders
GET  /api/v1/customers/{customer_id}/orders/{order_id}
POST /api/v1/customers/{customer_id}/tickets
GET  /api/v1/customers/{customer_id}/tickets
GET  /api/v1/customers/{customer_id}/tickets/{ticket_id}
GET  /api/v1/policies/search?q=refund&limit=5
POST /api/v1/customers/{customer_id}/tickets/{ticket_id}/resolution-preview
```

Ticket creation uses the customer ID in the path. Order and ticket reads are
customer-scoped and return `404` when the record is missing or owned by another
customer.

## Deterministic order rules

`app/services/order_rules.py` evaluates cancellation, refunds, returns, damaged
replacements, and delivery dates without an LLM or database side effect.

Current demo policy:

- Cancellation: `pending` or `processing`, within 24 hours of placement.
- Refund, return, replacement: delivered order, within 30 days of delivery.
- Damaged replacement: matching support ticket plus confirmed damage evidence.
- Window boundaries are inclusive.
- Every evaluation receives `now`; rules never read the system clock.

Rules return stable decision codes. Allowed risky actions still require the
future approval workflow; these rules do not mutate orders or issue refunds.

## Policy knowledge base

Policies live in the directory configured by `POLICY_DIR` (default:
`policies`). Each Markdown file requires `id` and `title` front matter. Search is
deterministic, uses bounded heading-aware chunks, and returns citations such as
`policies/returns.md#L10-L11`. Missing policy directories return an empty result.

## Resolution preview

The resolution-preview endpoint accepts an action and explicit timestamps, then
combines deterministic order eligibility with up to three policy matches. It
returns a recommendation, stable rule code, rationale, and citations. Preview
requests do not create proposals, mutate orders, or execute refunds; human
approval remains a later workflow step.
