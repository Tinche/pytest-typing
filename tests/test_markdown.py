"""Tests for the Markdown parser."""

import textwrap

from pytest_typing._mypy import MypyChecker
from pytest_typing._ty import TyChecker
from pytest_typing.plugin import (
    MdCodeBlock,
    MdSection,
    concatenate_for_checker,
    group_blocks_by_section,
    parse_markdown,
)


def test_single_block() -> None:
    """Basic Markdown block parsing works."""
    md = textwrap.dedent("""\
        # My Test

        ```py
        x: int = 1
        ```
    """)
    blocks = parse_markdown(md)
    assert len(blocks) == 1
    assert blocks[0].source == "x: int = 1"
    assert blocks[0].section == "My Test"
    assert blocks[0].only_checkers is None
    assert blocks[0].skip_checkers == set()
    md = textwrap.dedent("""\
        # Suite

        ## Integers

        ```py
        x: int = 1
        ```

        ## Strings

        ```py
        y: str = "hi"
        ```
    """)
    blocks = parse_markdown(md)
    assert len(blocks) == 2
    assert blocks[0].section == "Suite - Integers"
    assert blocks[1].section == "Suite - Strings"


def test_non_python_blocks_ignored() -> None:
    """Non-Python blocks are ignored."""
    md = textwrap.dedent("""\
        ```toml
        [tool.ty]
        ```

        ```py
        x = 1
        ```
    """)
    blocks = parse_markdown(md)
    assert len(blocks) == 1


def test_empty_markdown() -> None:
    assert parse_markdown("") == []


def test_only_attribute() -> None:
    """The `only` attribute is properly parsed."""
    md = textwrap.dedent("""\
        ```py only=ty,pyright
        x = 1
        ```
    """)
    blocks = parse_markdown(md)
    assert len(blocks) == 1
    assert blocks[0].only_checkers == {"ty", "pyright"}


def test_skip_attribute() -> None:
    """The `skip` attribute is properly parsed."""
    md = textwrap.dedent("""\
        ```py skip=mypy
        x = 1
        ```
    """)
    blocks = parse_markdown(md)
    assert len(blocks) == 1
    assert blocks[0].skip_checkers == {"mypy"}


def test_attributes_are_per_block() -> None:
    """Attributes are scoped per-block."""
    md = textwrap.dedent("""\
        ```py only=ty
        x = 1
        ```

        ```py
        y = 2
        ```
    """)
    blocks = parse_markdown(md)
    assert len(blocks) == 2
    assert blocks[0].only_checkers == {"ty"}
    assert blocks[1].only_checkers is None


def test_group_blocks_empty() -> None:
    """Grouping empty list returns empty list."""
    assert group_blocks_by_section([]) == []


def test_group_blocks_single_section() -> None:
    """All blocks in same section are grouped together."""
    blocks = [
        MdCodeBlock("a = 1", 5, "Test", None, set()),
        MdCodeBlock("b = 2", 10, "Test", None, set()),
    ]
    sections = group_blocks_by_section(blocks)
    assert len(sections) == 1
    assert sections[0].name == "Test"
    assert len(sections[0].blocks) == 2


def test_group_blocks_multiple_sections() -> None:
    """Blocks in different sections create separate groups."""
    blocks = [
        MdCodeBlock("a = 1", 5, "Section A", None, set()),
        MdCodeBlock("b = 2", 10, "Section B", None, set()),
        MdCodeBlock("c = 3", 15, "Section B", None, set()),
    ]
    sections = group_blocks_by_section(blocks)
    assert len(sections) == 2
    assert sections[0].name == "Section A"
    assert len(sections[0].blocks) == 1
    assert sections[1].name == "Section B"
    assert len(sections[1].blocks) == 2


def test_group_blocks_no_section() -> None:
    """Blocks without a section (empty string) are grouped together."""
    blocks = [
        MdCodeBlock("a = 1", 5, "", None, set()),
        MdCodeBlock("b = 2", 10, "", None, set()),
    ]
    sections = group_blocks_by_section(blocks)
    assert len(sections) == 1
    assert sections[0].name == ""
    assert len(sections[0].blocks) == 2


def test_concatenate_single_block() -> None:
    """Single block is returned as-is."""
    block = MdCodeBlock("a = 1", 5, "Test", None, set())
    section = MdSection("Test", [block])
    result = concatenate_for_checker(section, TyChecker)
    assert result is block  # Same object


def test_concatenate_multiple_blocks() -> None:
    """Multiple blocks are concatenated with line preservation."""
    # Block 1 at line 5: "a = 1"
    # Block 2 at line 8: "b = 2"
    blocks = [
        MdCodeBlock("a = 1", 5, "Test", None, set()),
        MdCodeBlock("b = 2", 8, "Test", None, set()),
    ]
    section = MdSection("Test", blocks)
    result = concatenate_for_checker(section, TyChecker)

    assert result is not None
    assert result.start_line == 5
    # Lines 5, 6, 7, 8 -> "a = 1", "", "", "b = 2"
    lines = result.source.splitlines()
    assert lines[0] == "a = 1"  # line 5
    assert lines[1] == ""  # line 6 (padding)
    assert lines[2] == ""  # line 7 (padding)
    assert lines[3] == "b = 2"  # line 8


def test_concatenate_filters_by_only() -> None:
    """Blocks with `only` are filtered per checker."""
    blocks = [
        MdCodeBlock("a = 1", 5, "Test", None, set()),  # all checkers
        MdCodeBlock("b = 2", 8, "Test", {"mypy"}, set()),  # mypy only
        MdCodeBlock("c = 3", 11, "Test", None, set()),  # all checkers
    ]
    section = MdSection("Test", blocks)

    # For ty: should get blocks 1 and 3
    ty_result = concatenate_for_checker(section, TyChecker)
    assert ty_result is not None
    lines = ty_result.source.splitlines()
    assert lines[0] == "a = 1"  # line 5
    assert lines[6] == "c = 3"  # line 11

    # For mypy: should get all 3 blocks
    mypy_result = concatenate_for_checker(section, MypyChecker)
    assert mypy_result is not None
    lines = mypy_result.source.splitlines()
    assert lines[0] == "a = 1"  # line 5
    assert lines[3] == "b = 2"  # line 8
    assert lines[6] == "c = 3"  # line 11


def test_concatenate_filters_by_skip() -> None:
    """Blocks with `skip` are filtered per checker."""
    blocks = [
        MdCodeBlock("a = 1", 5, "Test", None, set()),  # all checkers
        MdCodeBlock("b = 2", 8, "Test", None, {"ty"}),  # skip ty
    ]
    section = MdSection("Test", blocks)

    # For ty: should only get block 1
    ty_result = concatenate_for_checker(section, TyChecker)
    assert ty_result is not None
    assert ty_result.source == "a = 1"  # single block, returned as-is

    # For mypy: should get both blocks
    mypy_result = concatenate_for_checker(section, MypyChecker)
    assert mypy_result is not None
    lines = mypy_result.source.splitlines()
    assert lines[0] == "a = 1"
    assert lines[3] == "b = 2"


def test_concatenate_all_filtered_returns_none() -> None:
    """If all blocks are filtered out, return None."""
    blocks = [
        MdCodeBlock("a = 1", 5, "Test", {"mypy"}, set())  # mypy only
    ]
    section = MdSection("Test", blocks)

    result = concatenate_for_checker(section, TyChecker)
    assert result is None
