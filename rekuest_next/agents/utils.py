from typing import Optional, List
from rekuest_next.api.schema import PortInput, StateSchemaInput


def resolve_port_for_path(schema: StateSchemaInput, path: str) -> Optional[PortInput]:
    """
    Resolves the specific Port definition for a given JSON path within the State Schema.

    This function traverses the schema tree. If the path points to a specific field
    (e.g., "/users/0/name"), it returns the Port for 'name'.
    If the path points to a list item (e.g., "/users/0"), it typically returns the
    List Port itself, as that port carries the structural definition (children)
    required to understand or shrink the item.

    Args:
        schema (StateSchemaInput): The root state schema.
        path (str): The RFC 6902 JSON Patch path (e.g., "/agent/position").

    Returns:
        Optional[PortInput]: The found port, or None if the path is invalid/unknown.
    """
    if not path or path == "/":
        return None

    # 1. Normalize Path: Remove leading slash and split
    # Example: "/users/0/name" -> ["users", "0", "name"]
    parts = path.strip("/").split("/")

    # 2. Start Search Context
    # We look for top-level ports first
    current_search_scope = schema.ports
    found_port: Optional[PortInput] = None

    for i, part in enumerate(parts):
        # --- Case A: List Index (Digit or Append '-') ---
        if part.isdigit() or part == "-":
            # If we see an index, we must be inside a List.
            # The first child of a list port describes the item type,
            # which is the correct port to shrink for list items.
            if found_port and found_port.children:
                found_port = found_port.children[0]
                # Update search scope for nested fields within the list item
                if found_port.children:
                    current_search_scope = found_port.children
            continue

        # --- Case B: Field Key (String) ---
        # We search the current scope (a tuple of ports) for a matching key.
        match = next((p for p in current_search_scope if p.key == part), None)

        if not match:
            # Path segment not found in the current schema level.
            return None

        # We found a match! Update our pointer.
        found_port = match

        # Update the search scope for the *next* iteration.
        # If this port has children (Structure or List), the next key should be inside them.
        if found_port.children:
            current_search_scope = found_port.children
        else:
            # If we hit a leaf but there are more parts, the path is invalid
            # (unless the next part is an index and this is a list, covered above).
            if i < len(parts) - 1:
                # Look ahead: if next part is NOT an index, we are stuck.
                next_part = parts[i + 1]
                if not (next_part.isdigit() or next_part == "-"):
                    # We have nowhere deeper to go
                    pass

    print(f"Mapped {path} to port:", found_port)  # Debug statement
    return found_port
