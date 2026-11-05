# 🛡️ ResolveAI

> A customer-support resolution copilot built with a production-minded backend architecture. Combines policy retrieval, deterministic business rules, LangGraph orchestration, and human approval workflows.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-green.svg)](https://github.com/langchain-ai/langgraph)
[![SQLite](https://img.shields.io/badge/SQLite-07405E.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

## Overview

**ResolveAI** is a customer-support resolution copilot designed for production-grade agentic workflows. It combines policy retrieval, customer and order tools, deterministic business rules, LangGraph orchestration, human approval gates, and evaluation frameworks into a unified support resolution system.

Currently in active development — the backend foundation is complete with domain contracts, SQLite persistence, and validated API schemas.

## ✨ Features

- **🚀 FastAPI Backend** — Async, production-ready API with automatic OpenAPI docs
- **📋 Domain Contracts** — Validated customer, product, order, ticket, proposal, and audit models
- **🗄️ SQLite Persistence** — SQLAlchemy ORM with repository pattern and deterministic demo seeding
- **📋 Pydantic Schemas** — Request/response validation with type safety
- **🔄 LangGraph Orchestration** — Agent-based resolution workflows (planned)
- **👥 Human Approval** — Deterministic approval gates for sensitive operations (planned)
- **📊 Evaluation** — Built-in evaluation framework for resolution quality (planned)

## 📁 Project Structure

```
resolve-ai/
├── app/                    # FastAPI application
│   ├── __init__.py
│   ├── main.py             # Application entry point
│   ├── api/                # Versioned API routes
│   ├── core/               # Configuration, security, dependencies
│   ├── models/             # SQLAlchemy database models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business logic services
│   └── repositories/       # Data access layer
├── policies/               # Deterministic policy knowledge base
├── tests/                  # Unit and integration tests
├── .env.example            # Environment variables template
├── .gitignore
├── .graphifyignore
├── AGENTS.md               # AI agent instructions
├── pyproject.toml
└── README.md
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | SQLite |
| Data Validation | Pydantic |
| Agent Orchestration | LangGraph (planned) |
| Package Manager | uv / pip |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip or uv

### Installation

```bash
# Clone the repository
git clone https://github.com/19anveshh/resolve-ai.git
cd resolve-ai

# Install dependencies
pip install -r requirements.txt
# or: uv sync

# Set up environment variables
cp .env.example .env
```

### Run the Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload

# or using uv
uv run uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs` for interactive API documentation.

## 📋 API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/...` | Various | Versioned API endpoints |

Current milestone includes:
- Health endpoint
- Versioned API structure
- Validated domain models
- Deterministic policy knowledge base
- Order rules and resolution preview workflow

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=app tests/
```

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 📬 Contact

**Anvesh Maddela** — B.Tech CSE | AI Engineering Student

- [GitHub](https://github.com/19anveshh)
- [Portfolio](https://github.com/19anveshh/19anveshh-Portfolio)
- [Email](mailto:19anveshh@gmail.com)

---

Building production-grade AI agent systems, one component at a time.