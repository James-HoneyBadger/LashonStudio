"""
ParserCraft Incremental Parsing

Provides incremental re-parsing for IDE/editor scenarios where the user
is continuously editing source code. Instead of re-parsing the entire file
on every keystroke, only the affected region is re-parsed and the AST is
patched in place.

Architecture:
    IncrementalParser wraps a PEGInterpreter and maintains:
        - The current full AST
        - A mapping of source regions → AST nodes
        - A dirty flag + edit log for coalescing edits

    On each edit (insert/delete), it:
        1. Records the edit range
        2. Identifies the smallest enclosing AST node
        3. Re-parses just that node's source region
        4. Splices the new subtree into the full AST

    Falls back to full re-parse when incremental fails.

Usage:
    from parsercraft.parser.incremental import IncrementalParser
    
    parser = IncrementalParser(grammar)
    ast = parser.parse("x = 10 ;\\ny = 20 ;")
    
    # User inserts " + 5" after "10"
    ast = parser.apply_edit(offset=6, old_len=0, new_text=" + 5")
    # Only the first statement is re-parsed
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from parsercraft.parser.grammar import Grammar, PEGInterpreter, SourceAST

logger = logging.getLogger(__name__)


@dataclass
class SourceEdit:
    """Describes a single edit operation on the source text."""
    offset: int     # Byte offset where edit starts
    old_len: int    # Number of characters removed
    new_text: str   # Text inserted at offset
    timestamp: float = field(default_factory=time.time)

    @property
    def new_len(self) -> int:
        return len(self.new_text)

    @property
    def delta(self) -> int:
        """Change in document length."""
        return self.new_len - self.old_len


@dataclass
class ASTRegion:
    """Maps a source region to an AST node for incremental updates."""
    start: int
    end: int
    node: SourceAST
    rule_name: str

    @property
    def length(self) -> int:
        return self.end - self.start

    def contains(self, offset: int) -> bool:
        return self.start <= offset < self.end

    def overlaps(self, start: int, end: int) -> bool:
        return self.start < end and start < self.end


class IncrementalParser:
    """Incremental parser that minimizes re-parsing on edits.

    Maintains the current AST and source text, and on each edit,
    identifies the smallest affected region and re-parses only that.
    """

    def __init__(self, grammar: Grammar, debounce_ms: int = 50):
        self._grammar = grammar
        self._interpreter = PEGInterpreter(grammar)
        self._source = ""
        self._ast: Optional[SourceAST] = None
        self._regions: List[ASTRegion] = []
        self._pending_edits: List[SourceEdit] = []
        self._debounce_ms = debounce_ms
        self._last_parse_time: float = 0.0
        self._parse_count: int = 0
        self._incremental_count: int = 0
        self._fallback_count: int = 0

    @property
    def ast(self) -> Optional[SourceAST]:
        """Current AST (may be None if not yet parsed)."""
        return self._ast

    @property
    def source(self) -> str:
        """Current source text."""
        return self._source

    @property
    def stats(self) -> Dict[str, Any]:
        """Parsing statistics."""
        return {
            "total_parses": self._parse_count,
            "incremental": self._incremental_count,
            "full_reparse": self._fallback_count,
            "last_parse_ms": self._last_parse_time * 1000,
        }

    def parse(self, source: str) -> SourceAST:
        """Full parse of source text. Initial parse or reset."""
        self._source = source
        t0 = time.time()
        self._ast = self._interpreter.parse(source)
        self._last_parse_time = time.time() - t0
        self._parse_count += 1
        self._build_regions(self._ast)
        return self._ast

    def apply_edit(self, offset: int, old_len: int, new_text: str) -> SourceAST:
        """Apply an edit and return the updated AST.

        Args:
            offset: Character offset where the edit starts
            old_len: Number of characters deleted at offset
            new_text: Text inserted at offset

        Returns:
            Updated AST
        """
        edit = SourceEdit(offset=offset, old_len=old_len, new_text=new_text)

        # Apply the edit to the source text
        old_source = self._source
        self._source = (
            old_source[:offset]
            + new_text
            + old_source[offset + old_len:]
        )

        # Try incremental parse
        t0 = time.time()
        success = self._try_incremental(edit, old_source)
        self._last_parse_time = time.time() - t0
        self._parse_count += 1

        if success:
            self._incremental_count += 1
        else:
            # Fall back to full re-parse
            self._fallback_count += 1
            try:
                self._ast = self._interpreter.parse(self._source)
                self._build_regions(self._ast)
            except SyntaxError as error:
                # Keep the old AST on parse errors (the user is mid-edit).
                logger.debug("Full reparse failed; keeping previous AST: %s", error)

        return self._ast

    def apply_edits(self, edits: List[Tuple[int, int, str]]) -> SourceAST:
        """Apply multiple edits in order.

        Args:
            edits: List of (offset, old_len, new_text) tuples,
                   sorted by offset descending (so later edits don't
                   shift earlier ones).
        """
        # Sort edits by offset descending to avoid offset shifting
        sorted_edits = sorted(edits, key=lambda e: e[0], reverse=True)

        for offset, old_len, new_text in sorted_edits:
            self.apply_edit(offset, old_len, new_text)

        return self._ast

    def _try_incremental(self, edit: SourceEdit, old_source: str) -> bool:
        """Attempt incremental re-parse of the affected region.

        Returns True if incremental parse succeeded, False if full
        re-parse is needed.
        """
        if not self._ast or not self._regions:
            return False

        # Find the smallest region containing the edit
        affected = self._find_affected_region(edit)
        if not affected:
            return False

        # Adjust region boundaries for the edit delta
        region_start = affected.start
        region_end = affected.end + edit.delta

        # Ensure bounds are valid
        if region_start < 0 or region_end > len(self._source):
            return False

        region_text = self._source[region_start:region_end]

        # Try to re-parse just this region
        try:
            new_subtree = self._interpreter.parse_rule(
                affected.rule_name, region_text
            )
        except (SyntaxError, AttributeError):
            # If the interpreter doesn't support parse_rule,
            # or parsing fails, fall back
            return False

        # Replace the old node with the new subtree
        self._replace_node(affected.node, new_subtree)
        self._build_regions(self._ast)

        return True

    def _find_affected_region(self, edit: SourceEdit) -> Optional[ASTRegion]:
        """Find the smallest AST region affected by an edit."""
        edit_start = edit.offset
        edit_end = edit.offset + edit.old_len

        # Find all regions that overlap with the edit
        if edit.old_len == 0:
            # An insertion is a point: require a region that strictly
            # contains the offset, otherwise fall back to a full reparse.
            overlapping = [
                r for r in self._regions
                if r.start < edit_start < r.end
            ]
        else:
            overlapping = [
                r for r in self._regions
                if r.overlaps(edit_start, edit_end)
            ]

        if not overlapping:
            return None

        # Return the smallest overlapping region
        return min(overlapping, key=lambda r: r.length)

    def _replace_node(self, old_node: SourceAST, new_node: SourceAST) -> None:
        """Replace old_node with new_node in the AST tree."""
        if self._ast is None:
            return

        def _replace_in(parent: SourceAST) -> bool:
            for i, child in enumerate(parent.children):
                if child is old_node:
                    parent.children[i] = new_node
                    return True
                if _replace_in(child):
                    return True
            return False

        if self._ast is old_node:
            self._ast = new_node
        else:
            _replace_in(self._ast)

    def _build_regions(self, ast: SourceAST) -> None:
        """Build the region map from the AST.

        Uses node positions if available, otherwise estimates from
        the source text structure (statement boundaries).
        """
        self._regions.clear()

        if not ast:
            return

        # Build regions from top-level statement children
        # This is a heuristic — for more precise incremental parsing,
        # the grammar engine should track source positions
        offset = 0

        for child in ast.children:
            # Estimate the node's source region
            # Use the node's string representation to find it in source
            if hasattr(child, 'value') and child.value:
                start = self._source.find(str(child.value), offset)
                if start >= 0:
                    # Find the end of this statement (next semicolon or newline)
                    end = self._source.find(";", start)
                    if end < 0:
                        end = len(self._source)
                    else:
                        end += 1  # Include the semicolon

                    self._regions.append(ASTRegion(
                        start=start,
                        end=end,
                        node=child,
                        rule_name=child.node_type,
                    ))
                    offset = end

            # For compound nodes, use child traversal
            elif child.children:
                rule_name = child.node_type
                # Estimate region from first/last leaf values
                first_val = self._first_leaf_value(child)
                if first_val:
                    start = self._source.find(first_val, offset)
                    if start >= 0:
                        end = self._source.find(";", start)
                        if end < 0:
                            end = len(self._source)
                        else:
                            end += 1

                        self._regions.append(ASTRegion(
                            start=start,
                            end=end,
                            node=child,
                            rule_name=rule_name,
                        ))
                        offset = end

    @staticmethod
    def _first_leaf_value(node: SourceAST) -> Optional[str]:
        """Find the first leaf value in a subtree."""
        if node.value is not None and not node.children:
            return str(node.value)
        for child in node.children:
            v = IncrementalParser._first_leaf_value(child)
            if v:
                return v
        return None

    def invalidate(self) -> None:
        """Force a full re-parse on next edit."""
        self._regions.clear()

    def reset(self) -> None:
        """Reset parser state entirely."""
        self._source = ""
        self._ast = None
        self._regions.clear()
        self._pending_edits.clear()
        self._parse_count = 0
        self._incremental_count = 0
        self._fallback_count = 0
