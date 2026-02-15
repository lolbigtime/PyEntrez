"""Stdlib XML helpers — replaces xmltodict dependency."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


def sanitize_xml(xml_str: str) -> str:
    """Fix common malformed entities in XML returned by EDirect."""
    return re.sub(r"&(?!(amp|lt|gt|apos|quot);)", "&amp;", xml_str)


def parse_xml(xml_str: str) -> ET.Element:
    """Parse an XML string into an ElementTree root, sanitizing first."""
    return ET.fromstring(sanitize_xml(xml_str))


def elem_text(elem: ET.Element | None, default: str = "") -> str:
    """Return the text content of an element, or *default* if None."""
    if elem is None:
        return default
    return (elem.text or "").strip() or default


def elem_int(elem: ET.Element | None, default: int = 0) -> int:
    """Return the text content of an element as int, or *default*."""
    txt = elem_text(elem)
    if not txt:
        return default
    try:
        return int(txt)
    except ValueError:
        return default
