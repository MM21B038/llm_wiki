# llm-wiki

A local Wikipedia per workspace. Upload source documents; an LLM agent turns them into a linked graph of wiki pages (markdown + YAML infobox) instead of dumping the raw text.

Each workspace is its own knowledge base. The agent searches existing pages, updates matches, and creates new topic pages only when needed.

## How it works

1. Create a **workspace**.
2. Upload a `.txt` or `.md` **document**.
3. The file is split into ~4096-token chunks.
4. A wiki maintainer agent processes each chunk with tools: hybrid search (BM25 + embeddings), create, read, update, insert, and delete.
5. Pages are stored as `{uuid}.md` under `media/<workspace>/wiki/`, with frontmatter (`id`, `title`, `description`, `tags`) and a markdown body. Related pages link as `[title](id)`.

Raw uploads live in `media/<workspace>/raw/`.

Chat and embeddings go through an OpenAI-compatible API — by default [OpenRouter](https://openrouter.ai).

## Requirements

- Python **3.14+**
- [uv](https://docs.astral.sh/uv/)
- An [OpenRouter](https://openrouter.ai) API key (or any OpenAI-compatible provider)

## Setup

```bash
git clone <repo-url>
cd llm_wiki
uv sync
```

Copy the env template and add your key:

```bash
cp .env.example .env
```

Apply migrations and start the API:

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

The API is at `http://127.0.0.1:8000`. Django admin is at `/admin/` (create a superuser with `uv run python manage.py createsuperuser` if you need it).

## Environment

`wiki/services/agent.py` and `wiki/tools.py` load `.env` via `python-dotenv`.

| Variable | Purpose |
|----------|---------|
| `LLM` | Chat model slug used by the wiki maintainer agent |
| `EMB` | Embedding model slug used for semantic search |
| `BASE_URL` | OpenAI-compatible API base URL |
| `API_KEY` | Provider API key |

`.env.example` ships with OpenRouter defaults:

```
LLM="nvidia/nemotron-3-ultra-550b-a55b:free"
EMB="nvidia/nemotron-3-embed-1b:free"
BASE_URL="https://openrouter.ai/api/v1"
API_KEY=""
```

Do not commit `.env`. Keep `.env.example` as the template.

## OpenRouter

1. Create an account at [openrouter.ai](https://openrouter.ai).
2. Create a key at [openrouter.ai/keys](https://openrouter.ai/keys).
3. Put the key in `.env` as `API_KEY`.
4. Leave `BASE_URL` as `https://openrouter.ai/api/v1`.

Model slugs are OpenRouter IDs (see [openrouter.ai/models](https://openrouter.ai/models)). The defaults are free NVIDIA Nemotron models. Change `LLM` / `EMB` to any chat and embedding models your key can call.

The same `BASE_URL` and `API_KEY` are passed to Composer `Agent` (generation) and `Vector` (embeddings). Any OpenAI-compatible host works if you point `BASE_URL` at it and use that provider’s model names.

## API

Prefix: `/wiki/`

### Workspaces

```bash
# List
curl http://127.0.0.1:8000/wiki/workspace/

# Create
curl -X POST http://127.0.0.1:8000/wiki/workspace/ \
  -H "Content-Type: application/json" \
  -d '{"name": "research", "description": "Notes and papers"}'

# Get workspace + documents
curl http://127.0.0.1:8000/wiki/workspace/research/

# Delete
curl -X DELETE http://127.0.0.1:8000/wiki/workspace/research/
```

Deleting a workspace also removes its files under `media/<name>/`.

### Documents

Upload is `multipart/form-data`. `workspace` is the workspace **name**. Only `.txt` and `.md` are chunked and sent to the agent.

```bash
curl -X POST http://127.0.0.1:8000/wiki/document/ \
  -F "workspace=research" \
  -F "file=@notes.md"
```

The document status moves from `pending` → `processing` while chunks run, then each chunk is marked `completed`. Wiki pages appear under `media/research/wiki/`.

```bash
curl -X DELETE http://127.0.0.1:8000/wiki/document/1/
```

## Layout

```
media/<workspace>/raw/     uploaded sources
media/<workspace>/wiki/    generated wiki pages ({uuid}.md)
wiki/                      Django app (API, models, agent, tools)
llm_wiki/                  Django project settings
```
