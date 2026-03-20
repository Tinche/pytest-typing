# Example Tests

These are the most basic tests we have. Snippets in here will run on all our supported checkers.

## First, simple test

A simple snippet, well-typed, just should work.

```python
a: int = 1
```

## Error checking failure

We can expect errors in snippets with in-line comments.
Checkers usually have incompatible error codes, so each checker gets its own dedicated prefix.

```python
a: str = 1  # ty-error: [invalid-assignment]  # mypy-error: [assignment]  # pyrefly-error: [bad-assignment]  # pyright-error: [reportAssignmentType]
```

## Errors above

We can expect errors on lines above.

```python
# ty-error: [invalid-assignment]
# mypy-error: [assignment]
# pyrefly-error: [bad-assignment]
# pyright-error: [reportAssignmentType]
a: str = 1
```

## Type reveals

Type reveals using `# revealed:` works properly.

```python
from typing_extensions import reveal_type

reveal_type(1)  # revealed: Literal[1]
```

## Reveals on the next line

We can also match reveals on the next line.

```python
from typing_extensions import reveal_type

# revealed: Literal["a"]
reveal_type("a")
```
