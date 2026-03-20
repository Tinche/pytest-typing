# *pytest-typing*: Test Your Types

*Ensure your types do what you think they do.*

[![License: MIT](https://img.shields.io/badge/license-MIT-C06524)](https://github.com/Tinche/pytest-typing/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/pytest_typing.svg)](https://pypi.python.org/pypi/pytest_typing)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/pytest_typing.svg)](https://github.com/python-attrs/pytest_typing)
[![Coverage](https://img.shields.io/badge/coverage-100%25-green)](https://github.com/Tinche/pytest_typing/actions/workflows/main.yml)

---

<!-- begin-teaser -->

**pytest-typing** lets you test the type signatures of your code to ensure they really are what you expect.
You write Markdown files with Python code blocks and expected type assertions;
_pytest-typing_ runs type checkers on these blocks and compares the actual and expected outputs.

<!-- end-teaser -->

First, install the plugin, making it discoverable by _pytest_:

```bash
$ pip install pytest-typing
$ # or
$ uv add pytest-typing --group dev
```

Then, configure _pytest-typing_ with the type checker (or checkers) you want to use in `pyproject.toml`:

```toml
[tool.pytest]
typing_checkers = ["mypy"]
```

The currently supported type checkers are [Mypy](https://mypy.readthedocs.io/en/stable/), [ty](https://docs.astral.sh/ty/),
[Pyrefly](https://pyrefly.org/), and [Pyright](https://microsoft.github.io/pyright/).

Finally, start writing Markdown files in your test directory (`tests/` by default).
The files need to be named `test_typing_*.md` in order to be collected.

Inside the Markdown file, use Markdown headings (`#`, `##`, etc.) to separate tests.
Inside each heading, write fenced Python code blocks (`python` or `py`) with code that will be type-checked.

This is what an example file might look like, defining two tests:

````markdown
# This is a test file

This is free-form text that can explain the test but is ignored by the plugin.

## This is a happy-path test

This code snippet should type-check without problems.

```python
a: int = 1
```

## This is a sad-path test

This test demonstrates how errors can be checked using error codes.
Note that error codes are specific to individual type checkers.

```python
a: str = 1  # error: [invalid-assignment]
```
````

In addition to matching on error codes, we can additionally match the exact error messages too.

```python
a: str = 1  # error: [invalid-assignment] Object of type `Literal[1]` is not assignable to `str`
```

Although this may be fragile since checkers can improve their error messages from time to time.

Comments may be placed above lines that are expected to produce errors.

```python
# error: [invalid-assignment]
a: str = 1
```

`reveal_type` statements can be matched against.

```python
reveal_type(1)  # revealed: Literal[1]
```

Or, again, on the line above.

```python
# revealed: Literal[1]
reveal_type(1)
```

A section may contain multiple code blocks; this is useful for inserting longer pieces of prose in between blocks.
All blocks within a section get concatenated.


````markdown
# This test contains multiple blocks

```python
a: int = 1
```

Here's some prose explaining what's going on, and then a second block:

```python
b: str = 1  # error: [invalid-assignment]
```
````

## Testing on multiple checkers

When the `typing_checkers` field is configured with multiple checkers, tests will be run on all of them.
Difference checkers usually have different error codes, so different error comments should be used.

```python
a: str = 1  # ty-error: [invalid-assignment]  # mypy-error: [assignment]
```

Or, when more checkers are in use, stacked:

```python
# ty-error: [invalid-assignment]
# mypy-error: [assignment]
# pyrefly-error: [bad-assignment]
# pyright-error: [reportAssignmentType]
a: str = 1
```

A code block can be configured to run only on a specific checker:

````markdown
```python only=mypy
a: int = 1
```
````

Or configured to skip only a specific checker:

````markdown
```python skip=mypy
a: int = 1
```
````

_pytest-typing_ is inspired by Astral's [mdtest framework](https://github.com/astral-sh/ruff/tree/main/crates/ty_test).

## Project Information

- [**PyPI**](https://pypi.org/project/pytest-typing/)
- [**Source Code**](https://github.com/Tinche/pytest-typing)
- [**Changelog**](https://github.com/Tinche/pytest-typing/blob/main/CHANGELOG.md)

## License

_pytest-typing_ is written by [Tin Tvrtković](https://threeofwands.com/) and distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
