#!/usr/bin/env python3
"""A small YAML reader for configuration files, using only the standard library.

Every skill here runs with a bare Python 3 and no install step, which is what
makes "clone it and the suite passes" true. Depending on PyYAML would trade
that for features this project does not use.

The cost is that the accepted subset is a decision rather than an inheritance,
so it is written down — in docs/spec/configuration.md §6 and in these
functions. Anything outside the subset raises rather than being guessed at:
misreading a configuration file is worse than refusing it, because a
misread produces behaviour nobody asked for and no error to search for.

Specification: docs/spec/configuration.md (`CFG`), §6.
"""

from __future__ import annotations

INDENT = 2


class YamlError(ValueError):
    """A file outside the supported subset, or malformed within it."""

    def __init__(self, message, line_number=None):
        if line_number is not None:
            message = f"line {line_number}: {message}"
        super().__init__(message)
        self.line_number = line_number


def parse(text):
    """Parse the supported subset and return plain Python values."""
    lines = _significant_lines(text)
    if not lines:
        return {}
    value, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise YamlError("unexpected content after the document", lines[index][2])
    return value


# --------------------------------------------------------------------- reading


def _significant_lines(text):
    """Return (indent, content, line_number) for each meaningful line."""
    out = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip("\t "))]:
            raise YamlError("tabs are not supported for indentation", number)
        if raw.strip() == "---" or raw.strip() == "...":
            raise YamlError("multi-document files are not supported", number)

        content = _strip_comment(raw).rstrip()
        if not content.strip():
            continue

        indent = len(content) - len(content.lstrip(" "))
        if indent % INDENT:
            raise YamlError(f"indentation must be a multiple of {INDENT} spaces", number)
        out.append((indent, content.strip(), number))
    return out


def _strip_comment(line):
    """Remove a trailing comment, respecting quotes."""
    quote = None
    for position, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (position == 0 or line[position - 1] in " \t"):
            return line[:position]
    return line


# --------------------------------------------------------------------- parsing


def _parse_block(lines, index, indent):
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines, index, indent):
    result = {}
    while index < len(lines):
        line_indent, content, number = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise YamlError("unexpected indentation", number)
        if content.startswith("- "):
            break

        key, raw_value = _split_key(content, number)
        if raw_value == "":
            nested_index = index + 1
            if nested_index < len(lines) and lines[nested_index][0] > line_indent:
                result[key], index = _parse_block(lines, nested_index, lines[nested_index][0])
            else:
                result[key] = None
                index = nested_index
        else:
            result[key] = _scalar(raw_value, number)
            index += 1
    return result, index


def _parse_list(lines, index, indent):
    items = []
    while index < len(lines):
        line_indent, content, number = lines[index]
        if line_indent < indent or not content.startswith("- "):
            break
        if line_indent > indent:
            raise YamlError("unexpected indentation", number)

        item = content[2:].strip()
        if ":" in item and not item.startswith(('"', "'")):
            # An inline mapping opening a list item: "- name: a" plus any
            # following lines indented under it.
            item_indent = line_indent + INDENT
            synthetic = [(item_indent, item, number)]
            index += 1
            while index < len(lines) and lines[index][0] >= item_indent and not lines[index][
                1
            ].startswith("- "):
                synthetic.append(lines[index])
                index += 1
            parsed, _ = _parse_mapping(synthetic, 0, item_indent)
            items.append(parsed)
        else:
            items.append(_scalar(item, number))
            index += 1
    return items, index


def _split_key(content, number):
    quote = None
    for position, char in enumerate(content):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == ":":
            return content[:position].strip(), content[position + 1 :].strip()
    raise YamlError("expected 'key: value'", number)


def _scalar(text, number):
    if text.startswith("&"):
        raise YamlError("anchors are not supported", number)
    if text.startswith("*"):
        raise YamlError("aliases are not supported", number)
    if text.startswith("{"):
        raise YamlError("flow mappings are not supported; use indentation", number)
    if text.startswith("["):
        if text.replace(" ", "") == "[]":
            return []
        raise YamlError("flow sequences are not supported; use a '- ' list", number)

    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]

    lowered = text.lower()
    if lowered in ("null", "~", ""):
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    try:
        return int(text)
    except ValueError:
        return text
