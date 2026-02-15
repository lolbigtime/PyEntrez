"""elink XML → dict mapping."""

from __future__ import annotations

from pyentrez._parsers._xml import elem_text, parse_xml


def parse_elink_xml(xml_str: str) -> dict[str, list[str]]:
    """Parse elink XML output into ``{source_id: [linked_ids]}``."""
    root = parse_xml(xml_str)
    result: dict[str, list[str]] = {}

    # Root is <eLinkResult> containing <LinkSet> elements
    link_sets = root.findall("LinkSet") if root.tag == "eLinkResult" else []
    if root.tag == "LinkSet":
        link_sets = [root]

    for link_set in link_sets:
        # Source ID
        id_list = link_set.find("IdList")
        if id_list is None:
            continue
        source_id_elem = id_list.find("Id")
        source_id = elem_text(source_id_elem)
        if not source_id:
            continue

        # Linked IDs
        linked_ids: list[str] = []
        link_set_db = link_set.find("LinkSetDb")
        if link_set_db is not None:
            for link in link_set_db.findall("Link"):
                lid = elem_text(link.find("Id"))
                if lid:
                    linked_ids.append(lid)

        result[source_id] = linked_ids

    return result
