# Hotel Booking AI Agent

An intelligent, conversational hotel booking assistant powered by LangGraph, OpenAI GPT-4o-mini, and Redis. The agent understands natural language, orchestrates tools dynamically, maintains multi-turn context, and caches API results for fast responses.

## Features

- Natural Language Understanding — Ask anything about hotels in plain English
- Dynamic Tool Orchestration — Automatically calls the right tools in the right order
- Multi-Turn Context — Remembers your preferences across the conversation
- Redis Caching — Sub-millisecond responses for repeated queries
- Graceful Error Handling — Friendly fallbacks for missing data or unavailable services

## Architecture

```
User -> Chainlit UI -> Agent Controller -> LangGraph Workflow
                                              |
                        +---------------------+--------------------+
                        |                     |                    |
                  Intent Detection      Tool Execution      Response Generation
                        |                     |
                        v                     v
                  Conditional Edge      Redis Cache -> Mock API
```

### LangGraph Workflow

The agent uses a directed graph with 5 node types:

| Node | Purpose |
|------|---------|
| Intent Detection | Classifies user intent using OpenAI |
| search_hotels | Finds hotels by city and dates |
| check_availability | Gets room types and pricing |
| get_hotel_details | Returns amenities, policies, landmarks |
| Response Generation | Composes natural language replies |

## Project Structure

```
Hotel-booking-ai-agent/
├── app.py                  # Chainlit entry point
├── chainlit.md             # Welcome page
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
│
├── agent/
│   └── controller.py       # Session and workflow orchestration
│
├── graph/
│   └── workflow.py         # LangGraph directed graph definition
│
├── state/
│   └── agent_state.py      # AgentState TypedDict
│
├── tools/
│   └── hotel_tools.py      # 3 tools with Redis cache-first pattern
│
├── cache/
│   └── redis_client.py     # Redis client with fail-open behavior
│
├── api/
│   └── mock_api.py         # Mock hotel API (JSON data source)
│
└── data/
    └── hotels.json         # Mock hotel inventory (6 hotels, 3 cities)
```

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv myvenv
myvenv\Scripts\Activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
copy .env.example .env
```

Edit `.env` and set your `OPENAI_API_KEY`.

### 4. Set up Redis (required for caching)

Redis must be running before you start the app. Choose one of the following options:

**Option A — Native Windows installer (recommended)**

Download and install the Windows Redis build from:
https://github.com/tporadowski/redis/releases

Run the MSI installer. Redis will start automatically as a Windows service on port `6379`.

Verify it is working:
```bash
"C:\Program Files\Redis\redis-cli.exe" ping
# Expected output: PONG
```

**Option B — Docker Desktop**

If Docker Desktop is installed and running:
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

**Option C — Run without caching**

If Redis is not available, the app will automatically fall back to direct API calls on every request. No configuration change is needed — the system handles this gracefully.

### 5. Run the app

```bash
myvenv\Scripts\chainlit.exe run app.py
```

Open `http://localhost:8000` in your browser.

When Redis is connected, the terminal will show:
```
redis connected
```

When running without Redis, it will show:
```
redis not available, running without cache
```

## Example Conversation

```
User: Find me hotels in Jaipur from Dec 10 to Dec 13 for 2 guests
Bot:  [Lists 3 hotels with ratings, locations, and prices]

User: Tell me about Maharani Palace
Bot:  [Shows amenities, policies, and nearby landmarks]

User: What rooms are available and how much do they cost?
Bot:  [Shows room types, availability counts, and pricing tiers]

User: What is the cancellation policy?
Bot:  [Answers from cached state — no additional API call needed]
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | — |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

## Caching Strategy

| Tool | Cache Duration | Reason |
|------|---------------|--------|
| search_hotels | 10 minutes | Search results are moderately stable |
| check_availability | 5 minutes | Room counts change frequently |
| get_hotel_details | 30 minutes | Amenities and policies rarely change |

## Limitations and Mock Data

This project uses static hotel data instead of a live hotel API. Keep the following in mind:

| Constraint | Details |
|------------|---------|
| Limited cities | Only Jaipur, Udaipur, and Goa are available |
| Limited hotels | 6 hotels total (3 in Jaipur, 2 in Udaipur, 1 in Goa) |
| Static inventory | Room counts and pricing do not change in real-time |
| No real booking | The agent can search and answer questions but cannot process actual reservations |
| No cross-session memory | Each new chat session starts fresh |

To connect a live hotel API in production, replace the functions in `api/mock_api.py` with real HTTP calls. The rest of the architecture (caching, state, LangGraph workflow) remains unchanged.

## Tech Stack

- LangGraph — Stateful workflow orchestration
- LangChain + OpenAI GPT-4o-mini — LLM for intent detection and response generation
- Redis — In-memory caching with TTL policies
- Chainlit — Chat UI framework
- Python 3.10+
