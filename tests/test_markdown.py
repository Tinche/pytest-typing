"""Tests for the Markdown parser."""

import textwrap

from pytest_typing.plugin import parse_markdown


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
