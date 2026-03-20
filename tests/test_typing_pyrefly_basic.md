# Tests for the Pyrefly backend

These are tests that only run on Pyrefly.

## Basic assignment error

```python only=pyrefly
a: str = 1  # pyrefly-error: [bad-assignment]
```

## Type reveals

```python only=pyrefly
from typing_extensions import reveal_type

reveal_type(1)  # revealed: Literal[1]
```

## Reveals on the next line

```python only=pyrefly
from typing_extensions import reveal_type

# revealed: Literal["a"]
reveal_type("a")
```
