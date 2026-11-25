# Knowledge Base and RAG API Contract

All routes below are under `/api/v1` and require a Firebase ID token in the
`Authorization: Bearer <token>` header. The server derives the business context
and permissions from the verified token and membership; clients must not send a
trusted `business_id` in a request body.

## Business Knowledge Base

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/businesses/{business_id}/documents` | Knowledge viewer | List documents |
| POST | `/businesses/{business_id}/documents` | Knowledge manager | Upload multipart field `file`; text is extracted and indexed if RAG is configured |
| GET | `/businesses/{business_id}/documents/{document_id}` | Knowledge viewer | Get document and extraction/indexing status |
| GET | `/businesses/{business_id}/documents/{document_id}/download` | Knowledge viewer | Download original file |
| POST | `/businesses/{business_id}/documents/{document_id}/retry` | Knowledge manager | Retry extraction; automatically reindexes on success when RAG is configured |
| POST | `/businesses/{business_id}/documents/{document_id}/index` | Knowledge manager | Index or retry indexing an extracted document |
| POST | `/businesses/{business_id}/documents/{document_id}/reindex` | Knowledge manager | Rebuild vectors from the current extracted text |
| GET | `/businesses/{business_id}/documents/{document_id}/index-status` | Knowledge viewer | Read extraction and indexing status |
| DELETE | `/businesses/{business_id}/documents/{document_id}` | Knowledge manager | Delete document, extracted text, and vectors |
| GET | `/businesses/{business_id}/knowledge` | Knowledge viewer | List structured knowledge entries |
| POST | `/businesses/{business_id}/knowledge` | Knowledge manager | Create entry; automatically indexes when RAG is configured |
| PATCH | `/businesses/{business_id}/knowledge/{entry_id}` | Knowledge manager | Update entry and synchronize its vectors |
| POST | `/businesses/{business_id}/knowledge/{entry_id}/index` | Knowledge manager | Index or retry indexing an entry |
| DELETE | `/businesses/{business_id}/knowledge/{entry_id}` | Knowledge manager | Delete entry and its vectors |

Document extraction status (`status`) and RAG indexing status
(`indexing_status`) are independent. Indexing status is `pending`, `processing`,
`indexed`, or `failed`. A processed document's response also includes
`indexed_chunk_count`, `indexed_at`, `indexing_error`, and `embedding_model`.
Structured entries expose equivalent indexing fields. Storage paths and vector
database credentials are never returned.

## RAG query

`POST /businesses/{business_id}/rag/query` requires the knowledge-view
permission. The owner/admin/member membership check is the authorization
boundary; the backend applies the verified business ID as a mandatory Qdrant
filter before returning passages.

Request:

```json
{
  "question": "What time does the restaurant open?",
  "top_k": 5
}
```

`question` is required (2-4000 characters); `top_k` is optional (1-20).

Response:

```json
{
  "answer": "The restaurant opens at 9 AM.",
  "sufficient_context": true,
  "sources": [
    {
      "source_type": "document",
      "business_id": "verified-business-id",
      "chunk_id": "document:document-id:0",
      "chunk_index": 0,
      "excerpt": "Opening hours: 9 AM to 6 PM.",
      "score": 0.83,
      "document_id": "document-id",
      "knowledge_entry_id": null,
      "document_name": "hours.txt",
      "title": null,
      "page_number": null
    }
  ]
}
```

When no passages meet the configured score threshold, the response has an empty
`sources` list, `sufficient_context: false`, and a no-information answer.
Retrieved passages are treated as untrusted reference data, not instructions.

## Configuration and deployment

Set these variables on the backend only; do not expose them to the browser:

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | unset | Required to enable RAG |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Supports `text-embedding-3-small` or `text-embedding-3-large`; vectors use 1536 dimensions |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Chat completion model |
| `QDRANT_URL` | unset | Required to enable RAG |
| `QDRANT_API_KEY` | unset | Optional for local Qdrant; use a key for hosted Qdrant |
| `QDRANT_COLLECTION` | `business_knowledge` | Shared collection; payload indexes are created by the service |
| `RAG_CHUNK_SIZE` | `1000` | Character chunk size |
| `RAG_CHUNK_OVERLAP` | `150` | Must be smaller than chunk size |
| `RAG_TOP_K` | `5` | Default number of retrieved chunks (1-20) |
| `RAG_MIN_SCORE` | `0.2` | Cosine-score cutoff (0-1) |

Create a Qdrant collection only if needed; the application creates it on first
use with 1536-dimensional cosine vectors. All app-managed points include
business/source identifiers and the API's search filters by business before
context reaches the language model. If the RAG credentials are absent, Phase 3
document and knowledge operations continue to work; indexing remains pending
and query/index endpoints return `503 rag_not_configured`.

The UI's **RAG Playground** uses the active business ID, displays the answer
with its retrieved excerpts, and clears its state when the active business
changes.

## Agents and conversations

Every route in this section requires Firebase authentication and the business
`agents:manage` permission (currently business owners and admins). A business
member without that permission receives `403`. The `business_id` in a URL is
only a lookup scope: backend authorization uses the caller's verified
membership. Agent and conversation IDs from another business return `404`.

Agents are stored at
`businesses/{business_id}/agents/{agent_id}`. Conversations are stored at
`businesses/{business_id}/conversations/{conversation_id}`, with messages in
the conversation's `messages` subcollection. Deleting an agent also deletes
its conversations and messages.

| Method | Path | Purpose |
|---|---|---|
| POST | `/businesses/{business_id}/agents` | Create an active agent |
| GET | `/businesses/{business_id}/agents` | List this business's agents |
| GET | `/businesses/{business_id}/agents/{agent_id}` | Get an agent configuration |
| PATCH | `/businesses/{business_id}/agents/{agent_id}` | Update configuration |
| PATCH | `/businesses/{business_id}/agents/{agent_id}/status` | Activate or deactivate |
| DELETE | `/businesses/{business_id}/agents/{agent_id}` | Delete agent and all its conversations/messages |
| POST | `/businesses/{business_id}/agents/{agent_id}/chat` | Test an active agent and persist a chat turn |
| GET | `/businesses/{business_id}/agents/{agent_id}/conversations` | List recent conversations for that agent |
| GET | `/businesses/{business_id}/conversations/{conversation_id}` | Get a conversation and up to 100 recent messages |
| DELETE | `/businesses/{business_id}/conversations/{conversation_id}` | Delete that conversation and its messages |

### Create agent

Request:

```json
{
  "name": "Restaurant Assistant",
  "description": "Answers questions about the restaurant.",
  "agent_type": "Restaurant Assistant",
  "instructions": "Answer politely using the restaurant's knowledge base.",
  "personality": "Friendly",
  "greeting": "Hello! How can I help?",
  "language": "English",
  "model": "default",
  "temperature": 0.2,
  "response_length": "standard"
}
```

`name` (1-100 chars), `agent_type` (1-80), and `instructions` (1-6000) are
required. `description` is at most 1000 chars, `personality` 1-80,
`greeting` at most 1000, and `language` 2-60. Temperature is 0-1;
`response_length` is `short`, `standard`, or `long`. The client may send
`model: "default"` or the currently configured backend chat model only. The
backend chooses the model from `OPENAI_CHAT_MODEL`, never from an arbitrary
client-supplied identifier. Agent type is a label, not a separate runtime.

Response is `201 AgentOut`:

```json
{
  "agent_id": "generated-id",
  "business_id": "business-id",
  "name": "Restaurant Assistant",
  "description": "Answers questions about the restaurant.",
  "agent_type": "Restaurant Assistant",
  "instructions": "Answer politely using the restaurant's knowledge base.",
  "personality": "Friendly",
  "greeting": "Hello! How can I help?",
  "language": "English",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "response_length": "standard",
  "status": "active",
  "created_by": "verified-firebase-uid",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

PATCH configuration accepts a non-empty subset of the create fields. Status is
changed separately with `{"status":"active"}` or `{"status":"inactive"}`.
Inactive agents cannot be chatted with until activated.

### Chat and conversation responses

Send a message; omit `conversation_id` to start a new conversation:

```json
{
  "message": "What time do you open?",
  "conversation_id": "existing-conversation-id"
}
```

`message` is 1-4000 characters. The business scope is resolved from the
verified agent record, not from message input. The backend runs a linear
LangGraph flow: validate agent → call the registered business-knowledge
search tool → generate a grounded answer → validate and persist the turn.
History sent to the model is capped at eight messages; history retrieval
returns at most 100 recent messages. Only the fixed read-only knowledge search
tool is registered—there is no arbitrary code, shell, database, or HTTP tool.

`200 AgentChatOut`:

```json
{
  "conversation_id": "generated-or-existing-id",
  "user_message": {
    "message_id": "generated-message-id",
    "conversation_id": "generated-or-existing-id",
    "role": "user",
    "content": "What time do you open?",
    "sources": [],
    "created_at": "2026-01-01T00:00:00Z"
  },
  "assistant_message": {
    "message_id": "generated-message-id",
    "conversation_id": "generated-or-existing-id",
    "role": "assistant",
    "content": "We open at 9 AM.",
    "sources": [],
    "created_at": "2026-01-01T00:00:00.000001Z"
  }
}
```

`GET .../agents/{agent_id}/conversations` returns an array of
`ConversationOut` (up to 100, newest first), with `conversation_id`,
`business_id`, `agent_id`, `status`, timestamps, and a short last-message
preview. `GET .../conversations/{conversation_id}` returns
`{"conversation": ConversationOut, "messages": ConversationMessageOut[]}`.
Message sources use the same `RagSource` shape as the RAG query endpoint.
Delete operations return `204`.

Other relevant errors: `404 agent_not_found` / `conversation_not_found`,
`409 agent_inactive` / `business_archived`, `422 unsupported_agent_model` or
validation errors, and `503 agent_runtime_unavailable` for provider failures.

## Error behavior

Errors use the standard response shape:

```json
{"error":{"code":"rag_unavailable","message":"Knowledge search is temporarily unavailable."}}
```

Expect `401` for missing/invalid authentication, `403` for missing business
permissions, `404` for inaccessible or missing resources, `409` when a document
is not yet processed, `422` for invalid request values, and `503` when RAG is
unconfigured or an embedding/vector/answer provider is unavailable.
