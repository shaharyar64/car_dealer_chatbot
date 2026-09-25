# Car Dealer Chatbot

An LLM-powered chatbot that helps users find cars from an inventory and connects them with the
dealers who sell them: search by make, model, budget, body type or city, see dealer details, and
schedule a call. Available as a Streamlit web app (with temporary, session-based chat history) and
a CLI.

## Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [How the Chatbot Works](#how-the-chatbot-works)
- [Data Design](#data-design)
- [Running the Project](#running-the-project)
- [Testing](#testing)
- [Edge Cases](#edge-cases)
- [Design Decisions](#design-decisions)
- [Important Notes](#important-notes)

## Features

- Natural-language car search (make, model, budget, body type, city — several at once)
- Car details, comparisons and dealer inventory ("what else does this dealer sell?")
- Dealer search and details (name, city, phone, email)
- Call scheduling ("Friday at 3pm" → a confirmed date and time)
- Multi-turn, context-aware conversation: follow-ups, corrections and references
  ("the second one", "only BMW") without repeating information
- Chat history sidebar with automatic titles, rename and delete
- Temporary, session-based memory — conversations last for the active browser session, so
  context (and follow-ups like "show me more") works within a chat, without a database
- Session-isolated conversations (no login required)

## Tech Stack

- **Python 3.10+**
- **Streamlit** — web UI and in-memory session state for chat history
- **LangChain + OpenAI** (`gpt-4o-mini` by default) — structured intent extraction via tool-calling
- **python-dotenv** — configuration
- **pytest, black, ruff** — testing, formatting and linting

## Project Structure

```
car_dealer_chatbot/
├── data/                    # cars.csv, dealers.csv — sample inventory
├── src/car_dealer_chatbot/
│   ├── chatbot.py           # conversation logic: context, references, replies
│   ├── intents.py           # the Intent a message is interpreted as
│   ├── repository.py        # CSV loading and fuzzy car search
│   ├── scheduling.py        # turns an extracted date/time into a real datetime
│   ├── llm/                 # LangChain/OpenAI client, prompts, tool schemas
│   ├── services/            # runs a chat turn, auto titles, service wiring
│   ├── storage/             # in-memory conversation/message store (per chat session)
│   ├── ui/                  # Streamlit screens (sidebar, chat page, session, theme)
│   ├── cli.py, webapp.py    # CLI and web app entry points
│   └── config.py            # environment variable handling
├── scripts/setup.py         # one-command setup (venv, dependencies)
├── tests/                   # pytest suite
└── docs/                    # architecture diagram and project plan
```

## Setup

**Prerequisites**: Python 3.10+ and an [OpenAI API key](https://platform.openai.com/api-keys).
No database is required — chat history is kept temporarily in memory for the active session.

1. **Get the code**
   ```bash
   git clone https://github.com/shaharyar64/car_dealer_chatbot.git
   cd car_dealer_chatbot
   ```
2. **Create `.env` from the template**
   ```bash
   cp .env.example .env              # Windows PowerShell: Copy-Item .env.example .env
   ```
3. **Fill in the required value** in `.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```
4. **Run the setup script**
   ```bash
   python scripts/setup.py           # macOS/Linux: use python3 if python isn't found
   ```
   This creates the `.venv` virtual environment and installs all dependencies. It is safe to
   run again at any time (e.g. after pulling new changes).

Prefer to do it yourself? `python -m venv .venv`, activate it, then `pip install -e ".[dev]"`.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | yes | – | OpenAI API key used by LangChain |
| `LLM_MODEL` | no | `gpt-4o-mini` | OpenAI model |
| `CARS_DATA_PATH` | no | `data/cars.csv` | Car inventory CSV |
| `DEALERS_DATA_PATH` | no | `data/dealers.csv` | Dealer CSV |
| `LOG_LEVEL` | no | `INFO` | Log detail written to `logs/chatbot.log` |

Never commit `.env` — it already is in `.gitignore`.

## How the Chatbot Works

```
User message → conversation context (from this session's temporary in-memory history)
             → LangChain / OpenAI (interprets the message: intent + car/filter details)
             → matching action (search, dealer lookup, scheduling — using the CSV data)
             → templated reply
             → added to the session's temporary conversation history
```

A bare number ("2") or small talk ("hi", "thanks") is answered directly, without calling the LLM.
Otherwise, one LLM call classifies the message into an intent (search, select a car, dealer
details, schedule a call, …) with any relevant details; the chatbot resolves references against
the conversation and writes the reply from a fixed template — the LLM extracts, it does not
generate the response text. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full diagram.

## Data Design

Two CSV files under `data/`, loaded once at startup:

```
data/cars.csv                              data/dealers.csv
  car_id, make, model, variant,               dealer_id, name, city,
  year, price, body_type,      ────┐          phone, email
  dealer_id                        │
                                    └──────►  cars.dealer_id == dealers.dealer_id
```

Every car's `dealer_id` is expected to match a row in `dealers.csv`; there's no foreign-key
constraint enforcing this (it's plain CSV, not a database), so `repository.py` logs a warning and
skips a car row it can't parse, and the chatbot reports (rather than guesses at) a car whose
dealer can't be found. The shipped data has 78 cars, 22 dealers and 26 makes, with every
`dealer_id` resolving correctly.

## Running the Project

```bash
# Windows
.venv\Scripts\python.exe -m streamlit run src/car_dealer_chatbot/webapp.py
# macOS / Linux
.venv/bin/python -m streamlit run src/car_dealer_chatbot/webapp.py
```

Opens at `http://localhost:8501`. Stop with **Ctrl+C**; restart after changing code (Streamlit
doesn't reload the package automatically).

A CLI is also available (`.venv\Scripts\car-dealer-chatbot.exe` on Windows,
`.venv/bin/car-dealer-chatbot` on macOS/Linux). It only needs `OPENAI_API_KEY` — nothing is
saved, and it exits on `exit`/`quit`/Ctrl+C.

## Testing

```bash
pytest                                        # all tests
pytest --cov=src/car_dealer_chatbot tests/    # with coverage
```

All tests use a fake LLM client, so no OpenAI calls or API credits are used.

## Edge Cases

| Situation | Behaviour |
|---|---|
| Car not found (e.g. "Tesla Model 3") | A "couldn't find it" reply listing the makes in stock — never an invented car. |
| Typo (e.g. "Toyoto Corolla") | Fuzzy token matching (`repository.search_cars`) finds the intended car anyway. |
| Multiple matching cars | A numbered list is shown; the user picks one by number or narrows the search. |
| Invalid menu choice (e.g. "5" or "I don't know") | The bot asks the user to choose again instead of crashing. |
| Invalid/incomplete date-time (e.g. "sometime later") | The bot asks for a clearer date/time instead of fabricating one. |
| Empty or whitespace-only input | The bot asks the user to type a message; nothing is sent to the LLM. |
| LLM/API failure | Caught as `LLMError`, logged, and answered with a friendly retry message — no traceback or key is ever shown to the user. |
| Missing or empty car/dealer CSV data | `DataError` is raised at startup with a clear message instead of starting silently broken. |
| A car whose dealer can't be found | Reported to the user instead of guessed at; the bot still offers to search for another car. |

## Design Decisions

**The LLM extracts, it never invents.** `interpret_message` / `parse_datetime` return only
structured fields (intent, make/model, price range, date/time parts); every car, dealer, price
and phone number shown to the user is looked up from `data/cars.csv` / `data/dealers.csv` by
`repository.py` and formatted by fixed templates in `chatbot.py`. This guarantees the bot can
never state a car, dealer or contact detail that isn't actually in the inventory — the trade-off
is that the LLM has less freedom in how it phrases the reply text.

**Chat history is temporary, in-memory session state.** The Streamlit web app keeps conversations
in `st.session_state` for as long as the browser session lasts, so LangChain always has the
recent messages it needs for follow-ups — but nothing is written to disk or a database. Starting
a new chat, closing the tab, or restarting the app all start with a clean slate. This is a
deliberate simplification: no database to install, configure or keep running.

## Important Notes

- Scheduling only collects and confirms a date/time — nothing is sent to the dealer.
- Conversation history is kept only in memory, for the current Streamlit session; it is not
  persisted anywhere and does not survive a browser/session restart or an app restart.
- Check `logs/chatbot.log` for details when something goes wrong (e.g. an OpenAI error).