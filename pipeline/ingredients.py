"""Top-level ingredient list splitter handling nested parentheses, brackets, and full-width punctuation."""

from __future__ import annotations

import re


def split_top_level(text: str) -> list[str]:
    """Splits an ingredient string on top-level commas or semicolons.
    
    Sub-ingredients within (), [], or {} remain intact inside their parent item.
    Also handles full-width commas (，) and semicolons (；).
    """
    if not text:
        return []

    items: list[str] = []
    current: list[str] = []
    depth = 0

    # Map opening to closing delimiters
    bracket_pairs = {"(": ")", "[": "]", "{": "}"}
    opening_brackets = set(bracket_pairs.keys())
    closing_brackets = set(bracket_pairs.values())

    bracket_stack: list[str] = []

    # Delimiters that separate top-level items: comma, full-width comma, semicolon, full-width semicolon
    delimiters = {",", "，", ";", "；"}

    for char in text:
        if char in opening_brackets:
            bracket_stack.append(char)
            depth += 1
            current.append(char)
        elif char in closing_brackets:
            if bracket_stack and bracket_pairs.get(bracket_stack[-1]) == char:
                bracket_stack.pop()
                depth = max(0, depth - 1)
            current.append(char)
        elif depth == 0 and char in delimiters:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(char)

    last_item = "".join(current).strip()
    if last_item:
        items.append(last_item)

    return items
