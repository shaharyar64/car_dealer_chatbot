# Car Dealer Chatbot — TDD

**Status:** Implemented  
**Framework:** pytest  
**Purpose:** Define the automated tests that must be implemented for the Car Dealer Chatbot.

---

## 1. Test Files Created

```text
tests/
├── conftest.py               # Shared fixtures and fake LLM client
├── test_repository.py        # Car/dealer data loading and search
├── test_intents.py           # Intent interpretation
├── test_chatbot.py           # Conversation logic and flow
├── test_scheduling.py        # Date/time parsing and validation
├── test_conversation.py      # Multi-turn conversation scenarios
├── test_chat_service.py      # Chat service and session management
├── test_titles.py            # Chat title generation
├── test_openai_client.py     # LLM client parsing and error handling
├── test_ui_formatting.py     # UI formatting utilities
└── test_webapp.py            # Streamlit web interface
```

All tests use a fake/mock LLM client (FakeLLMClient in conftest.py) so the test suite does not depend on live OpenAI API calls.

---

## 2. Vehicle Search Tests

### `test_repository.py`

| Test | Expected Result |
|---|---|
| `test_search_car_by_make` | Returns cars matching the requested make |
| `test_search_car_by_model` | Returns cars matching the requested model |
| `test_search_car_by_price` | Returns only cars inside the requested price range |
| `test_search_car_by_body_type` | Returns only cars with the requested body type |
| `test_search_car_by_city` | Returns cars sold by dealers in the requested city |
| `test_search_with_combined_filters` | Applies make, model, price, body type, and city together |
| `test_search_is_case_insensitive` | `bmw` and `BMW` return the same matches |
| `test_search_handles_typo` | A clear spelling variation resolves to the intended vehicle |
| `test_search_returns_no_result` | Returns an empty result when no vehicle matches |
| `test_search_results_come_from_csv` | Every returned vehicle exists in the CSV inventory |

---

## 3. Dealer Tests

### `test_dealers.py`

| Test | Expected Result |
|---|---|
| `test_get_dealer_by_id` | Returns the correct dealer |
| `test_car_resolves_correct_dealer` | Selected car returns the dealer linked by `dealer_id` |
| `test_get_dealer_inventory` | Returns only cars belonging to the selected dealer |
| `test_missing_dealer_returns_error` | Missing dealer is handled without fabricated information |

---

## 4. Intent and LLM Tests

### `test_intents.py`

| Test | Expected Result |
|---|---|
| `test_search_intent` | Vehicle request is classified as search |
| `test_select_car_intent` | Numbered or named selection is classified correctly |
| `test_dealer_details_intent` | Dealer-information request is recognized |
| `test_schedule_call_intent` | Call scheduling request is recognized |
| `test_compare_intent` | Vehicle comparison request is recognized |
| `test_fact_and_search_in_same_message` | User fact and search request are both extracted |
| `test_context_reference_intent` | References such as `it` or `the second one` are interpreted correctly |
| `test_small_talk_does_not_require_tool` | Greeting/thanks are handled without inventory lookup |
| `test_invalid_llm_response_is_handled` | Invalid structured output returns a controlled error |

---

## 5. Conversation Flow Tests

### `test_chatbot.py`

| Test | Expected Result |
|---|---|
| `test_search_then_select_car` | User can search and select one returned vehicle |
| `test_select_car_then_show_dealer` | Dealer details are returned for the selected car |
| `test_search_then_schedule_call` | Scheduling flow starts for the selected car |
| `test_schedule_call_requests_datetime` | Missing date/time causes the chatbot to ask for it |
| `test_complete_schedule_flow` | Valid date/time returns a callback confirmation |
| `test_chatbot_handles_greeting` | Returns a normal greeting |
| `test_chatbot_handles_thanks` | Returns an acknowledgement |
| `test_chatbot_handles_goodbye` | Returns a goodbye without crashing or corrupting state |
| `test_out_of_scope_question` | Redirects unsupported requests appropriately |

---

## 6. Search Refinement Tests

### `test_context.py`

| Test | Expected Result |
|---|---|
| `test_refinement_preserves_previous_filters` | Existing compatible filters remain active |
| `test_refinement_updates_changed_filter` | New value replaces the previous value for the same filter |
| `test_switching_make_starts_new_search` | `Actually show Audis` replaces the previous BMW search |
| `test_relative_cheaper_search` | `Cheaper` uses the current vehicle price |
| `test_show_more_reuses_filters` | `Show me more` reuses the active search filters |
| `test_numbered_reference_uses_latest_results` | `2` selects the second vehicle from the latest result set |
| `test_it_resolves_current_car` | `Tell me about it` uses the selected car |
| `test_dealer_reference_uses_current_car` | `the dealer` resolves through the current car |

---

## 7. Session and Facts Tests

### `test_context.py`

| Test | Expected Result |
|---|---|
| `test_store_user_fact` | Stores a supplied fact such as budget |
| `test_recall_user_fact` | Returns a previously stored fact |
| `test_update_user_fact` | Replaces the old value with the new value |
| `test_multiple_facts_in_one_message` | Stores all facts extracted from one message |
| `test_new_session_has_empty_state` | New session starts without previous context |
| `test_sessions_are_isolated` | State from one session is not visible in another |

---

## 8. Scheduling Tests

### `test_scheduling.py`

| Test | Expected Result |
|---|---|
| `test_parse_explicit_datetime` | Parses a direct date/time correctly |
| `test_parse_relative_datetime` | Parses values such as `tomorrow at 10am` |
| `test_parse_weekday_datetime` | Parses `Friday at 3pm` |
| `test_reject_past_datetime` | Past date/time is rejected |
| `test_reject_incomplete_datetime` | Vague input requests clarification |
| `test_schedule_requires_selected_car` | Scheduling without a car asks the user to choose one |
| `test_pending_schedule_resumes_after_car_selection` | Pending schedule continues after vehicle selection |
| `test_schedule_confirmation_contains_dealer` | Confirmation includes dealer name and phone |
| `test_schedule_does_not_claim_real_booking` | Response does not claim an external booking was completed |

---

## 9. Error Handling Tests

### `test_errors.py`

| Test | Expected Result |
|---|---|
| `test_empty_input` | User is asked to enter a message |
| `test_invalid_result_number` | User is asked to select a valid result |
| `test_ambiguous_car_reference` | Chatbot asks which vehicle the user means |
| `test_missing_car_csv` | Application raises/returns controlled data error |
| `test_missing_dealer_csv` | Application raises/returns controlled data error |
| `test_malformed_csv` | Invalid source data is handled safely |
| `test_llm_api_failure` | Returns a friendly retry response |
| `test_repository_failure_does_not_fabricate_data` | No fake vehicle/dealer information is returned |

---

## 10. UI Tests

### `test_ui.py`

| Test | Expected Result |
|---|---|
| `test_chat_input_submits_message` | User message is submitted correctly |
| `test_bot_response_is_rendered` | Chatbot response is displayed |
| `test_new_chat_creates_fresh_session` | New chat starts with empty context |
| `test_error_message_is_rendered` | Controlled application errors are visible to the user |
| `test_chat_history_is_preserved_in_session` | Messages remain available during the active session |

---

## 11. Acceptance Test

### `test_end_to_end_assignment_flow`

```text
Bot:
Which car are you looking to buy?

User:
I'm interested in a Toyota Corolla.

Bot:
Returns the matching Toyota Corolla and dealer.

User:
Schedule a call.

Bot:
Asks for preferred date and time.

User:
Friday at 3pm.

Bot:
Returns the dealer name, phone number, and Friday 15:00 confirmation.
```

Expected:

- Vehicle exists in CSV.
- Correct dealer is resolved.
- Scheduling flow completes.
- No real external booking is attempted.
- No vehicle or dealer information is fabricated.

---

## 12. Completion Criteria

The test implementation is complete when:

- all planned test files exist;
- all listed core scenarios are covered;
- tests run without a live OpenAI API key;
- CSV search and dealer matching are deterministic;
- conversation context and session isolation are verified;
- scheduling edge cases are covered;
- failure paths are tested;
- `pytest` passes successfully.
