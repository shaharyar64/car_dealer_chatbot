"""Shared look and feel: brand mark and the CSS layered on top of the Streamlit theme.

Colors, font and radius live in .streamlit/config.toml; this module only adds what the
theme cannot express (chat bubbles, pill buttons, sidebar details).
Selectors target Streamlit's stable data-testid attributes and `st-key-<key>` classes.
"""

import html

import streamlit as st

APP_NAME = "Car Dealer Assistant"

_BASE_CSS = """
<style>
:root {
  --cda-primary: #2557d6;
  --cda-primary-hover: #1e47b3;
  --cda-primary-soft: #eef3fd;
  --cda-primary-border: #d5e0fa;
  --cda-text: #0f172a;
  --cda-muted: #64748b;
  --cda-border: #e2e8f0;
  --cda-surface: #ffffff;
  --cda-subtle: #f8fafc;
  --cda-shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.05);
  --cda-shadow-md: 0 1px 3px rgba(15, 23, 42, 0.06), 0 8px 24px rgba(15, 23, 42, 0.06);
}

header[data-testid="stHeader"] { background: transparent; }
[data-testid="stHeaderActionElements"] { display: none; }

/* ---------- Brand mark ---------- */
.cda-brand { display: flex; align-items: center; gap: 0.625rem; }
.cda-brand-mark {
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
  width: 2rem; height: 2rem; border-radius: 0.5rem;
  background: var(--cda-primary); color: #fff;
}
.cda-icon {
  font-family: "Material Symbols Rounded"; font-weight: normal; font-style: normal;
  line-height: 1; letter-spacing: normal; white-space: nowrap; font-feature-settings: "liga";
  -webkit-font-smoothing: antialiased; user-select: none;
}
.cda-brand-mark .cda-icon { font-size: 1.25rem; }
.cda-brand-name {
  font-weight: 600; font-size: 0.975rem; letter-spacing: -0.01em; color: var(--cda-text);
}

/* ---------- Pill buttons (suggestions, quick replies) ---------- */
.st-key-suggestions button, .st-key-quick_replies button {
  min-height: 2.25rem; padding: 0.375rem 0.875rem; border-radius: 999px;
  border: 1px solid var(--cda-border); background: var(--cda-surface);
  box-shadow: var(--cda-shadow-sm); color: var(--cda-text);
  transition: border-color 120ms ease, background-color 120ms ease, color 120ms ease;
}
.st-key-suggestions button p, .st-key-quick_replies button p { font-size: 0.875rem; font-weight: 500; }
.st-key-suggestions button:hover, .st-key-quick_replies button:hover {
  border-color: var(--cda-primary-border); background: var(--cda-primary-soft); color: var(--cda-primary);
}
.st-key-quick_replies { padding-left: 2.75rem; }

/* ---------- Alerts ---------- */
[data-testid="stAlertContainer"] { border-radius: 0.5rem; }

@media (max-width: 640px) {
  .st-key-quick_replies { padding-left: 0; }
}
</style>
"""

_CHAT_CSS = """
<style>
/* ---------- Header ---------- */
.st-key-chat_header, .st-key-welcome { flex: 0 0 auto; }
.st-key-chat_header { margin-bottom: 0.5rem; }
.st-key-chat_header h4 {
  padding: 0 0 0.75rem; border-bottom: 1px solid var(--cda-border); font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ---------- Messages ---------- */
[data-testid="stChatMessage"] {
  background: transparent; padding: 0.375rem 0; gap: 0.75rem; align-items: flex-start;
}
[data-testid="stChatMessageContent"] {
  flex: 0 1 auto; min-width: 0; max-width: min(85%, 42rem); margin: 0;
  padding: 0.75rem 1rem; border: 1px solid var(--cda-border);
  border-radius: 0.25rem 0.875rem 0.875rem 0.875rem;
  background: var(--cda-surface); box-shadow: var(--cda-shadow-sm);
}
[data-testid="stChatMessageContent"] p { font-size: 0.9375rem; line-height: 1.6; }
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p:last-child { margin-bottom: 0; }
[data-testid="stChatMessageContent"] [data-testid="stCaptionContainer"] p {
  margin-top: 0.125rem; font-size: 0.75rem; line-height: 1; color: var(--cda-muted);
}

[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) { flex-direction: row-reverse; }
[aria-label="Chat message from user"] {
  border-color: var(--cda-primary-border); background: var(--cda-primary-soft);
  border-radius: 0.875rem 0.25rem 0.875rem 0.875rem; box-shadow: none;
}
[aria-label="Chat message from user"] [data-testid="stCaptionContainer"] p { text-align: right; }

/* Avatars: a solid brand tile for the assistant, a neutral tile for the user. */
[data-testid="stChatMessage"] > [data-testid^="stChatMessageAvatar"] {
  width: 2rem; height: 2rem; border-radius: 0.5rem;
  background: var(--cda-subtle); color: #475569; border: 1px solid var(--cda-border);
}
[data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) > [data-testid^="stChatMessageAvatar"] {
  background: var(--cda-primary); color: #fff; border-color: var(--cda-primary);
}

/* Typing state */
[data-testid="stChatMessageContent"] [data-testid="stSpinner"] p,
[data-testid="stChatMessageContent"] [data-testid="stSpinner"] { font-size: 0.875rem; color: var(--cda-muted); }

/* ---------- Input ---------- */
[data-testid="stChatInput"] {
  border: 1px solid var(--cda-border); border-radius: 0.75rem;
  background: var(--cda-surface); box-shadow: var(--cda-shadow-md);
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--cda-primary); box-shadow: 0 0 0 3px rgba(37, 87, 214, 0.12);
}
[data-testid="stChatInputTextArea"] { font-size: 0.9375rem; }
[data-testid="stChatInputSubmitButton"] {
  border-radius: 0.5rem; background: var(--cda-primary); color: #fff;
}
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) { background: var(--cda-primary-hover); color: #fff; }
[data-testid="stChatInputSubmitButton"]:disabled { background: var(--cda-border); color: #94a3b8; }

/* ---------- Welcome screen ---------- */
.st-key-welcome { padding: 3.5rem 0 1rem; align-items: center; }
.st-key-welcome h2, .st-key-welcome p, .st-key-welcome [data-testid="stHtml"] { text-align: center; }
.st-key-welcome .cda-welcome-mark {
  display: inline-flex; align-items: center; justify-content: center;
  width: 3rem; height: 3rem; border-radius: 0.75rem;
  background: var(--cda-primary-soft); color: var(--cda-primary); border: 1px solid var(--cda-primary-border);
}
.st-key-welcome .cda-welcome-mark .cda-icon { font-size: 1.625rem; }
.st-key-welcome h2 { padding: 0.25rem 0 0; font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; }
.st-key-welcome [data-testid="stMarkdownContainer"] p {
  max-width: 32rem; margin: 0 auto; color: var(--cda-muted); font-size: 1rem; line-height: 1.6;
}
.st-key-welcome [data-testid="stCaptionContainer"] p {
  margin-top: 1rem; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: #94a3b8;
}

@media (max-width: 640px) {
  [data-testid="stChatMessageContent"] { max-width: 100%; }
  [data-testid="stChatMessage"] > [data-testid^="stChatMessageAvatar"] { display: none; }
  .st-key-welcome { padding-top: 1.5rem; }
  .st-key-welcome h2 { font-size: 1.5rem; }
}
</style>
"""

_SIDEBAR_CSS = """
<style>
[data-testid="stSidebar"] { border-right: 1px solid var(--cda-border); }
[data-testid="stSidebarUserContent"] { padding-top: 1rem; }
.st-key-sidebar_brand { padding-bottom: 0.25rem; }

.cda-section-label {
  margin: 0.75rem 0 0.25rem; font-size: 0.75rem; font-weight: 600;
  letter-spacing: 0.06em; text-transform: uppercase; color: #94a3b8;
}
.st-key-history [data-testid="stCaptionContainer"] { margin-bottom: 0; }
.st-key-history [data-testid="stCaptionContainer"] p {
  margin: 0.5rem 0 0 0.75rem; font-size: 0.75rem; font-weight: 500; color: var(--cda-muted);
}

/* History entries: left-aligned rows; the open chat is highlighted softly. */
[class*="st-key-conversation_"] button {
  justify-content: flex-start; padding: 0.45rem 0.75rem; min-height: 0;
  border: 1px solid transparent; border-radius: 0.5rem;
}
[class*="st-key-conversation_"] button > div { justify-content: flex-start; width: 100%; }
[class*="st-key-conversation_"] button p { text-align: left; line-height: 1.35; font-size: 0.875rem; }
[class*="st-key-conversation_"] button[kind="tertiary"] { color: var(--cda-text); }
[class*="st-key-conversation_"] button[kind="tertiary"]:hover { background: rgba(15, 23, 42, 0.05); }
[class*="st-key-conversation_"] button[kind="primary"],
[class*="st-key-conversation_"] button[kind="primary"]:hover {
  background: var(--cda-primary-soft); border-color: var(--cda-primary-border);
  color: var(--cda-primary); font-weight: 500;
}
[class*="st-key-conversation_"] button .stMarkdownColoredText { color: var(--cda-muted) !important; }

/* Each entry's '⋮' menu: shown on hover, for the open chat, and always on touch screens. */
[class*="st-key-history_row_"] [data-testid="stPopover"] {
  flex-shrink: 0; opacity: 0; transition: opacity 120ms ease;
}
[class*="st-key-history_row_"]:hover [data-testid="stPopover"],
[class*="st-key-history_row_"]:focus-within [data-testid="stPopover"],
[class*="st-key-history_row_"]:has(button[kind="primary"]) [data-testid="stPopover"] { opacity: 1; }
@media (hover: none) {
  [class*="st-key-history_row_"] [data-testid="stPopover"] { opacity: 1; }
}
[class*="st-key-history_row_"] [data-testid="stPopoverButton"] {
  min-height: 0; padding: 0.35rem 0.25rem; color: var(--cda-muted); border-radius: 0.5rem;
}
[class*="st-key-history_row_"] [data-testid="stPopoverButton"]:hover {
  color: var(--cda-text); background: rgba(15, 23, 42, 0.05);
}
/* Hide the dropdown chevron: the '⋮' icon is the whole button. */
[class*="st-key-history_row_"] [data-testid="stPopoverButton"] div[aria-hidden="true"] { display: none; }
[class*="st-key-conversation_"] button span[data-has-shortcut],
[class*="st-key-conversation_"] button [data-testid="stMarkdownContainer"] { width: 100%; }
[class*="st-key-conversation_"] button [data-testid="stMarkdownContainer"],
[class*="st-key-conversation_"] button [data-testid="stMarkdownContainer"] p { text-align: left !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-rename_"]) { min-width: 9rem; padding: 0.25rem; }
[data-testid="stPopoverBody"] [class*="st-key-rename_"] button,
[data-testid="stPopoverBody"] [class*="st-key-delete_"] button {
  justify-content: flex-start; padding: 0.4rem 0.6rem; min-height: 0; border-radius: 0.375rem;
}
[data-testid="stPopoverBody"] [class*="st-key-rename_"] button > div,
[data-testid="stPopoverBody"] [class*="st-key-delete_"] button > div { justify-content: flex-start; width: 100%; }
[data-testid="stPopoverBody"] [class*="st-key-rename_"] button:hover { background: rgba(15, 23, 42, 0.05); }
[data-testid="stPopoverBody"] [class*="st-key-delete_"] button { color: #dc2626; }
[data-testid="stPopoverBody"] [class*="st-key-delete_"] button:hover { background: rgba(220, 38, 38, 0.08); }
.st-key-delete_chat_actions button[kind="primary"] { background: #dc2626; border-color: #dc2626; }
.st-key-delete_chat_actions button[kind="primary"]:hover { background: #b91c1c; border-color: #b91c1c; }
</style>
"""


def _car_icon() -> str:
    # A Material Symbols ligature: Streamlit ships the font, and st.html strips inline SVG.
    return '<span class="cda-icon" aria-hidden="true">directions_car</span>'


def apply_base() -> None:
    """Styles shared by the chat area and the sidebar."""
    st.html(_BASE_CSS)


def apply_chat() -> None:
    st.html(_CHAT_CSS)


def apply_sidebar() -> None:
    st.html(_SIDEBAR_CSS)


def brand() -> None:
    """The logo mark and product name."""
    st.html(
        f'<div class="cda-brand"><span class="cda-brand-mark">{_car_icon()}</span>'
        f'<span class="cda-brand-name">{APP_NAME}</span></div>'
    )


def welcome_mark() -> None:
    st.html(f'<span class="cda-welcome-mark">{_car_icon()}</span>')


def section_label(text: str) -> None:
    st.html(f'<p class="cda-section-label">{html.escape(text)}</p>')
