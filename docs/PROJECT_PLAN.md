# Car Dealer Chatbot — Project Plan

## 1. Project Overview

An LLM-powered chatbot that helps a user find a car from an inventory, see the dealer who sells
it, and schedule a call with that dealer. It is built for a small dealership-style catalogue (CSV
data) and offered as both a Streamlit web app and a CLI.

## 2. Main Features

- Natural-language car search (make, model, budget, body type, city, several at once)
- Car details, comparisons, and "what else does this dealer sell?"
- Dealer search and details
- Call scheduling with natural-language date/time ("Friday at 3pm")
- Multi-turn, context-aware conversation: follow-ups, corrections, references ("the second one")
- Chat history per browser session, with automatic titles, rename and delete

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Language |
| Streamlit | Web UI and in-memory session state |
| LangChain + OpenAI (`gpt-4o-mini`) | Structured intent/detail extraction via tool-calling |
| CSV | Car and dealer inventory |
| pytest, black, ruff | Testing, formatting, linting |

## 4. Chatbot Architecture

```
Streamlit UI → Chat service → Chatbot (conversation logic) → LangChain/OpenAI (intent extraction)
                    ↓                       ↓
          Session memory (st.session_state)  repository.py (CSV search) + scheduling.py
```

- **Streamlit UI** (`ui/`): chat window, quick-reply buttons, history sidebar
- **Chat service** (`services/chat_service.py`): loads a conversation, runs one turn, saves the
  result — the only place that reads and writes the session's conversation store per message
- **Chatbot** (`chatbot.py`): the conversation logic. A bare number or small talk is answered
  without the LLM; anything else goes through the LLM to interpret the message, then Python
  resolves references, searches the inventory and writes the reply from a fixed template
- **LLM layer** (`llm/`): an abstract `LLMClient` interface with an `OpenAIClient` implementation
  (LangChain's `ChatOpenAI`, forced tool-calling). Swapping providers means adding one adapter class
- **Repository** (`repository.py`): loads the CSVs and does token-based fuzzy car search
  (`difflib`), tolerant of typos and partial names
- **Scheduling** (`scheduling.py`): the LLM only extracts date/time *parts* ("Friday", "3pm");
  Python resolves them into an actual datetime deterministically

See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the full request-flow diagram.

## 5. Conversation & Memory

- Each browser session gets its own in-memory `ConversationStore`, held in `st.session_state` —
  no database, no cookie, no visitor id
- Conversations are identified by a UUID; every lookup goes through the calling session's own
  store, so one session can never see another's chat
- The chatbot's state (cars last shown, car being discussed, active filters, last 20 messages,
  facts the user has shared) is saved as a dict on the conversation object and restored on every
  turn, so context is kept for the life of the session — but not across a restart
- The LLM only sees this state as a text summary — it never gets a raw dump of every message

## 6. Main Chatbot Capabilities

- **Car search** — filters by make/model, price range, body type and city; up to 5 matches shown
- **Car details** — full details of a selected or referenced car
- **Dealer search & details** — name, city, phone, email for a car's dealer
- **Scheduling** — asks for a time, resolves it, confirms the booking (nothing is sent to the
  dealer; this is a confirmation only, not a real booking system)
- **Context-aware follow-ups** — references ("that one", "the cheaper one"), corrections, and
  filter refinement ("only BMW") without repeating earlier details

## 7. Session Memory

The `ConversationStore` (`storage/memory_store.py`) holds what needs to be private per browser
session, in memory only:

- **Conversations** — id, title, saved chatbot state (a dict), timestamps
- **Messages** — id, conversation id, role (`user`/`assistant`), content, timestamp

Deleting a conversation removes its messages too. Everything lives in `st.session_state`, so it's
gone when the session ends or the app restarts. The car/dealer inventory itself stays in CSV
files — it's read-only reference data, not per-session state.

## 8. Project Structure

```
src/car_dealer_chatbot/
├── chatbot.py, intents.py, scheduling.py   # conversation logic
├── repository.py, models.py                # CSV data access
├── llm/                                    # LangChain/OpenAI client, prompts
├── services/                               # chat turn orchestration, auto titles
├── storage/                                # in-memory conversation/message store
├── ui/                                     # Streamlit screens
└── cli.py, webapp.py                       # entry points
tests/         # pytest suite
data/          # cars.csv, dealers.csv
scripts/       # setup.py — one-command project setup
```

## 9. Current Implementation Status

- Session-isolated chat history (no login, no database)
- Temporary, in-memory conversation memory via `st.session_state`
- LLM orchestration via LangChain's `ChatOpenAI` (structured extraction, not free-form generation)
- Context-aware conversation: references, corrections, recall of stated facts
- Car search, car details, dealer search/details and call scheduling
- Streamlit web app and CLI, both sharing the same chatbot core
- Automated test suite covering repository, chatbot logic, LLM client, scheduling, chat service,
  titles, UI formatting and the web app

## 10. Testing

- `tests/` holds ~10 files covering the repository, chatbot conversation logic, the LLM client,
  scheduling, the chat service, title generation, UI formatting and the web app
- All tests run against a fake LLM client — no OpenAI calls, no network dependency
- Chat-service and web-app tests use a fresh, in-memory `ConversationStore` per test — no
  database setup or teardown needed
- Run with `pytest`, or `pytest --cov=src/car_dealer_chatbot tests/` for coverage
