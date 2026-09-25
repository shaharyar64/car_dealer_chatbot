# Car Dealer Chatbot — L1 Specification

**Status:** Implemented  
**Level:** L1  
**Version:** v1

## 1. Purpose

The Car Dealer Chatbot is an LLM-powered application that helps users find available vehicles, identify the dealer selling a selected car, and request a dealer callback through a conversational interface.

The solution uses Python, LangChain, and CSV-based vehicle and dealer data.

## 2. Core Conversation Flow

```text
User enters a vehicle request
        ↓
Chatbot interprets the request
        ↓
Vehicle inventory is searched
        ↓
Matching vehicle and dealer are returned
        ↓
User chooses:
    - View dealer details
    - Schedule a call
```

For call scheduling:

```text
Schedule Call
    ↓
Collect preferred date and time
    ↓
Validate the requested slot
    ↓
Return confirmation with dealer details
```

No external booking or calendar integration is required.

## 3. Technology

- Python
- LangChain
- OpenAI-compatible LLM provider
- CSV-based vehicle and dealer data
- CLI interface
- Optional Streamlit web interface
- pytest

## 4. Project Structure

```text
src/car_dealer_chatbot/
├── core/
│   └── chatbot.py          # Conversation logic and state management
├── config/
│   ├── config.py           # Environment variables and configuration
│   └── logging_config.py   # Logging setup
├── models/
│   ├── models.py           # Car and Dealer dataclasses
│   ├── intents.py          # Intent definitions
│   └── scheduling.py       # Date/time parsing and resolution
├── data/
│   └── repository.py       # CSV loading and fuzzy car search
├── llm/                    # LangChain/OpenAI integration
│   ├── base.py            # Abstract LLM interface
│   ├── openai_client.py   # OpenAI implementation
│   └── prompts.py         # System prompts and tool schemas
├── services/              # Business logic and service layer
│   ├── chat_service.py    # Conversation management
│   ├── factory.py         # Dependency injection and wiring
│   └── titles.py          # Chat title generation
├── storage/               # Session state management
│   └── memory_store.py    # In-memory conversation store
└── ui/                    # User interface layer
    ├── cli.py             # Command-line interface
    ├── webapp.py          # Streamlit web app
    ├── chat_page.py       # Chat display components
    ├── sidebar.py         # Sidebar and history
    ├── session.py         # Streamlit session management
    ├── formatting.py      # Message formatting utilities
    └── theme.py           # UI theming
```

Supporting directories:

```text
data/       Vehicle and dealer CSV files
tests/      Automated tests
docs/       Supporting documentation
scripts/    Utility scripts
```

## 5. Data Model

### Vehicle

```text
car_id
make
model
variant
year
price
body_type
dealer_id
```

### Dealer

```text
dealer_id
name
city
phone
email
```

Vehicles are linked to dealers using `dealer_id`.

## 6. Vehicle Search

The chatbot supports natural-language search by:

- make
- model
- variant
- price
- body type
- dealer city

Search results must come from the CSV inventory.

The LLM must not generate vehicle, price, or dealer data.

## 7. Conversation Context

Each session maintains temporary conversation context, including:

```text
search filters
candidate vehicles
selected vehicle
selected dealer
user facts
recent conversation history
pending action
```

This enables follow-up requests such as:

```text
Show me BMWs.
Only SUVs.
What about the second one?
Who is the dealer?
```

Each session must remain isolated.

## 8. Vehicle and Dealer Details

Vehicle details may include:

```text
make
model
variant
year
price
body_type
dealer
```

Dealer details may include:

```text
name
city
phone
email
```

All values must be retrieved from application data.

## 9. LLM and LangChain Integration

LangChain is used to integrate the configured LLM with the chatbot application.

LangChain is responsible for:

- sending user messages and conversation context to the LLM
- structured intent extraction
- extracting vehicle filters and references
- extracting user facts
- identifying date/time information
- coordinating LLM-driven tool selection where required

The LLM is used for natural-language understanding only.

Authoritative vehicle, dealer, pricing, inventory, and scheduling data is retrieved through application services and CSV repositories.

## 10. Application Services

Core services include:

```text
search_inventory
get_car
get_dealer
list_dealer_inventory
compare_cars
create_call_request
```

The chatbot determines the required action and routes it to the appropriate service.

## 11. Call Scheduling

Users can request a dealer callback after selecting a vehicle.

Required information:

```text
vehicle
dealer
preferred date
preferred time
```

Flow:

```text
Select vehicle
    ↓
Choose Schedule Call
    ↓
Provide preferred date/time
    ↓
Validate input
    ↓
Return callback confirmation
```

The confirmation should include the dealer name, dealer phone number, and selected time.

This feature records or simulates a callback request only; it does not create a real external booking.

## 12. Configuration

Application configuration is loaded from environment variables.

Typical values include:

```text
OPENAI_API_KEY
LLM_MODEL
CARS_DATA_PATH
DEALERS_DATA_PATH
LOG_LEVEL
```

A `.env.example` file should document required variables.

Secrets must not be committed to version control.

## 13. Error Handling

The chatbot should handle:

- vehicle not found
- ambiguous vehicle matches
- missing dealer data
- invalid date/time
- empty input
- missing or malformed CSV files
- LLM/API failures
- application service failures

Errors must return clear user-facing messages without fabricating vehicle or dealer information.

## 14. Testing

Automated tests should cover:

- vehicle lookup
- dealer matching
- search filtering
- intent handling
- conversation context
- reference resolution
- date/time parsing
- call scheduling
- service failures
- session isolation

Core business logic should be testable without requiring live LLM API calls.

## 15. Acceptance Criteria

The implementation is complete when:

- users can search for vehicles using natural language
- results come only from CSV inventory
- the correct dealer is resolved for each selected vehicle
- dealer details can be displayed
- users can request a callback with a valid date and time
- conversation context supports follow-up requests
- sessions remain isolated
- invalid input and service failures are handled gracefully
- the LLM never fabricates vehicle, dealer, price, or scheduling data
- the project can be installed, configured, run, and tested using the README
