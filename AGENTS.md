# MivoAi Engineering Standard

This file is the canonical engineering contract for the repository. Read it
before adding a route, application use case, repository, Agent tool, or
frontend API module.

## System shape

MivoAi is one local modular monolith:

- Browser talks directly to FastAPI at `http://127.0.0.1:8010`.
- Next.js does not proxy `/api/*`.
- FastAPI is the only application API and exposes HTTP and WebSocket.
- ComfyUI uses `http://127.0.0.1:8000`.
- Codex App Server, ComfyUI, external model APIs, FFmpeg, SQLite, and workspace
  files are adapters behind ports.

Do not split this into microservices unless a concrete deployment or isolation
need requires it. Preserve boundaries so a context can be extracted later.

## Architecture style

Use a DDD-oriented modular monolith with domain modules first, centralized
delivery adapters, and centralized infrastructure adapters. A global
`api/services/crud/models/schema` layout is not permitted.

Canonical backend shape:

```text
app/
├── modules/
│   └── <domain>/
│       ├── domain.py         # Pure entities, value objects, policies, events
│       ├── application.py    # Use-case orchestration
│       ├── commands.py       # Optional application commands
│       └── ports.py          # Protocols required by the application
├── delivery/
│   ├── http/
│   │   ├── api.py            # Single HTTP route aggregation point
│   │   ├── routes/           # All public HTTP routes
│   │   ├── schemas/          # All HTTP request/response schemas
│   │   └── errors.py
│   └── agent/                # Agent tool adapters
├── adapters/
│   ├── persistence/
│   │   ├── database.py
│   │   └── sqlite/           # Repositories grouped by module
│   ├── codex/
│   ├── comfyui/
│   ├── providers/
│   ├── media/
│   └── workspaces/
├── shared/
├── composition.py
└── main.py
```

Small contexts may keep these as modules. When a module becomes too large,
convert it to a package with the same import path, for example:

```text
application/
├── __init__.py               # Stable public exports
├── commands/
└── use_cases/
```

Do not introduce a new top-level `api`, `contexts`, `db`, `infrastructure`,
`interfaces`, `models`, or `services` folder. Those compatibility layers have
been removed.

## Bounded contexts

The current module ownership is:

| Context | Owns |
| --- | --- |
| `conversations` | Product conversations, Codex threads, turns, messages, streams |
| `creative_projects` | Creative workspaces, document workflows, artifacts, quality gates |
| `drama` | Episodes, scenes, shots, production runs, review and rendering decisions |
| `providers` | Provider/model catalog, credentials, semantic capabilities, model routing |
| `workflows` | ComfyUI workflow discovery, import, graph conversion, parameter mapping |
| `media_generation` | Durable generation tasks, retries, cancellation and result binding |
| `assets` | Uploaded/generated files, metadata, local content lookup |
| `media_processing` | Deterministic media work: FFmpeg, TTS, subtitles, upscaling |
| `delivery/http/system.py` | Health and runtime diagnostics only |

Business behavior must live in the owning module. Do not add drama behavior to
`providers`, ComfyUI behavior to `drama`, or SQL to a route.

## Layer responsibilities

### Domain

- Contains business rules and framework-free data structures.
- Must not import FastAPI, Starlette, SQLite, HTTP clients, Uvicorn, adapters,
  or delivery code.
- Must not know about request aliases such as camelCase unless that name is
  genuinely part of the domain.

### Application

- Orchestrates one coherent use case or a small group of strongly related use
  cases.
- Owns validation that spans multiple domain objects and transaction-boundary
  decisions.
- Depends on `domain`, `ports`, and its own commands/query DTOs.
- Must not import HTTP schemas or concrete repositories.
- Must not import another module's repository or adapter.
- Large application modules must be split by use case instead of growing into a
  god service.

### Ports

- Define the smallest cross-boundary interface needed by the application.
- Prefer domain records or typed contracts over raw SQL rows.
- Concrete infrastructure may implement several ports when cohesive.

### HTTP delivery

- All HTTP discovery starts in `delivery/http/api.py`; routes live together in
  `delivery/http/routes`, and schemas live together in
  `delivery/http/schemas`.
- A route is a thin adapter: parse request, call one application method, then
  map domain/application errors to HTTP status codes.
- Pydantic request/response models belong in `delivery/http/schemas`.
- Routes must never import or access a repository, execute SQL, inspect files,
  or call ComfyUI directly.
- Route paths remain stable when internal modules are reorganized.

### Adapters

- Implements ports for SQLite, files, Codex, ComfyUI, HTTP models, FFmpeg, and
  operating-system services.
- Never contains product decisions such as script approval or shot readiness.
- Adapter-specific request formats and node IDs stay here or in the owning
  workflow/domain mapper.

## Dependency rules

Allowed direction:

```text
delivery/http or delivery/agent
        -> application
        -> domain + ports
        <- adapters implementations
```

The composition root is the only place that constructs concrete adapters and
application services.

- Cross-module calls use application contracts or ports.
- Cross-module payloads use stable IDs and explicit DTOs.
- Do not share tables or repositories across modules.
- Modules must not import `app.adapters` or `app.delivery`.
- Do not call the API over HTTP from an Agent tool; inject the application use
  case instead.

## CRUD and persistence

There is no global CRUD business layer.

- Use a Repository with business-relevant method names.
- Generic CRUD helpers may exist only as private infrastructure utilities.
- SQLite remains one physical database for now, but repositories are separated
  by context.
- Schema initialization and migrations stay in
  `app/adapters/persistence`.
- HTTP `schemas.py`, domain models, and database tables are different concepts
  and must not be treated as interchangeable.

## API contract

- One FastAPI process and one port: `8010`.
- `8000` belongs to ComfyUI.
- REST endpoints use `/api/...`.
- Conversation streaming may use the session WebSocket or the compatibility SSE
  endpoint. New clients should use the session WebSocket.
- A Codex model/provider configuration change must restart the App Server and
  create a new Codex Thread. Preserve local product history, but never resume a
  Thread across runtime signatures.
- Error responses must be actionable and preserve stable status codes.
- Background jobs are durable database records, not fire-and-forget tasks with
  no persisted state.

The frontend must use `NEXT_PUBLIC_API_BASE_URL` (default
`http://127.0.0.1:8010`). Do not restore a Next.js `/api` rewrite.

## Agent tools

- An Agent tool is an adapter over an application use case.
- HTTP and Agent entry points must invoke the same business operation.
- Tool schemas expose provider-neutral semantics, never ComfyUI node IDs.
- Destructive, paid, or GPU-heavy operations require explicit approval and
  idempotency.
- Tools must return durable task IDs and support status/result queries.
- Conversation workspaces are isolated; shared playbooks and tool docs are
  read-only shared resources.

## Frontend boundaries

- Browser API calls are centralized in `apps/web/shared/api`.
- HTTP and media URLs are resolved against the FastAPI base URL.
- Components may use presentation helpers from `shared/ui`; they must not
  import API modules directly.
- Feature modules own their hooks and state. `app/page.tsx` remains a route
  entry, not a utility dumping ground.

## Testing and verification

Every backend change must run:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
```

Every frontend change must run:

```powershell
cd apps/web
npm run check
npm run build
```

Tests must cover:

- domain policies without external services;
- application use cases with fake ports;
- repository behavior against a temporary SQLite database;
- route-to-use-case integration;
- Agent tool contracts where behavior changes;
- architecture dependency guards.

## Change discipline

- Do not recreate the removed compatibility directories.
- Migrate code into its owning module instead of adding exceptions.
- Keep API behavior stable unless the task explicitly changes it.
- Preserve user edits and unrelated worktree changes.
- When a module becomes too large, split by use case while keeping public import
  paths stable.
