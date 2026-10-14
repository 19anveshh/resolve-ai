# Graph Report - resolve-ai  (2026-10-14)

## Corpus Check
- 46 files · ~11,695 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 2, .example 1)

## Summary
- 529 nodes · 1478 edges · 22 communities (11 shown, 11 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 206 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- test_domain_models.py
- models.py
- routers/workflow.py
- field_validator
- PolicyKnowledgeBase
- OrderStatus
- opencode.json
- ResolveAI
- AGENTS.md
- resolve-ai
- test_db.py
- support.py
- test_resolution_workflow.py
- cancellation.md
- replacements.md
- returns.md

## God Nodes (most connected - your core abstractions)
1. `seed()` - 38 edges
2. `Order` - 34 edges
3. `PolicyKnowledgeBase` - 30 edges
4. `OrderStatus` - 29 edges
5. `RuleAction` - 26 edges
6. `SupportTicket` - 25 edges
7. `OrderRepository` - 24 edges
8. `evaluate_order_action()` - 24 edges
9. `Customer` - 23 edges
10. `AuditEvent` - 23 edges

## Surprising Connections (you probably didn't know these)
- `test_create_ticket_commits_and_returns_201()` --uses--> `TicketRow`  [INFERRED]
  tests/test_api.py → app/db/models.py
- `test_create_ticket_rejects_server_owned_or_path_owned_fields()` --uses--> `TicketRow`  [INFERRED]
  tests/test_api.py → app/db/models.py
- `test_schema_has_all_domain_tables()` --uses--> `Base`  [INFERRED]
  tests/test_db.py → app/db/base.py
- `test_resolution_preview_does_not_write_proposals()` --uses--> `Base`  [INFERRED]
  tests/test_workflow_api.py → app/db/base.py
- `_ticket_count()` --uses--> `TicketRow`  [INFERRED]
  tests/test_api.py → app/db/models.py

## Import Cycles
- None detected.

## Communities (22 total, 11 thin omitted)

### Community 0 - "test_domain_models.py"
Cohesion: 0.05
Nodes (45): ActionProposal, ActionType, ActorType, AuditEvent, AuditEventType, DomainModel, Order, OrderItem (+37 more)

### Community 1 - "models.py"
Cohesion: 0.06
Nodes (14): get_db(), enum_column(), create_database_engine(), get_session(), UTCDateTime, test_create_ticket_commits_and_returns_201(), test_create_ticket_rejects_server_owned_or_path_owned_fields(), test_ticket_with_unknown_order_returns_404_and_does_not_write() (+6 more)

### Community 2 - "routers/workflow.py"
Cohesion: 0.06
Nodes (8): get_policy_kb(), search_policies(), get_resolution_workflow(), preview_resolution(), get_settings(), Settings, about(), health_check()

### Community 3 - "field_validator"
Cohesion: 0.09
Nodes (7): _freeze_json(), normalize_currency(), normalize_email(), _require_timezone(), _thaw_json(), _utc_now(), ProductCreate

### Community 4 - "PolicyKnowledgeBase"
Cohesion: 0.06
Nodes (27): PolicyChunk, PolicyFrontMatter, PolicyMetadata, PolicySchemaModel, PolicySearchResponse, PolicySearchResult, _chunk_document(), flush() (+19 more)

### Community 6 - "OrderStatus"
Cohesion: 0.13
Nodes (26): OrderStatus, _allowed(), _as_utc(), DeliveryDateResult, DeliveryStatus, _deny(), evaluate_order_action(), OrderFacts (+18 more)

### Community 10 - "opencode.json"
Cohesion: 0.40
Nodes (4): plugin, $schema, skills, paths

### Community 11 - "ResolveAI"
Cohesion: 0.20
Nodes (9): Current milestone, Deterministic order rules, Local database, Policy knowledge base, Project structure, Resolution preview, ResolveAI, Run locally (+1 more)

### Community 20 - "test_db.py"
Cohesion: 0.06
Nodes (44): Base, ActionProposalRow, AuditEventRow, CustomerRow, OrderItemRow, OrderRow, ProductRow, TicketRow (+36 more)

### Community 23 - "support.py"
Cohesion: 0.18
Nodes (8): create_customer_ticket(), get_customer(), get_customer_order(), get_customer_ticket(), list_customer_orders(), list_customer_tickets(), _require_customer(), _ticket_error()

### Community 26 - "test_resolution_workflow.py"
Cohesion: 0.24
Nodes (12): ResolutionPreviewRequest, ResolutionPreviewResponse, ResolutionWorkflow, make_order(), make_ticket(), request_for(), test_explicit_policy_query_changes_retrieval(), test_preview_allows_refund_and_returns_policy_matches_and_citations() (+4 more)

## Knowledge Gaps
- **1 isolated node(s):** `resolve-ai`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 205 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PolicyKnowledgeBase` connect `PolicyKnowledgeBase` to `routers/workflow.py`, `test_resolution_workflow.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `seed()` (e.g. with `ActionProposalRow` and `AuditEventRow`) actually correct?**
  _`seed()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `resolve-ai` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_domain_models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05153576582148011 - nodes in this community are weakly interconnected._
- **Why does `Order` connect `test_domain_models.py` to `test_resolution_workflow.py`, `field_validator`, `test_db.py`, `OrderStatus`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Order` (e.g. with `OrderRepository` and `OrderFacts`) actually correct?**
  _`Order` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05844155844155844 - nodes in this community are weakly interconnected._