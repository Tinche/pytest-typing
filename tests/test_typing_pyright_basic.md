# Tests for the Pyright backend

These are tests that only run on Pyright.

## Simple assignment

```python only=pyright
a: int = 1
```

## Error message matching

In addition to matching on error codes, we can additionally match the exact error messages too.

```python only=pyright
a: str = 1  # error: [reportAssignmentType] Type "Literal[1]" is not assignable to declared type "str"
```

## reveal_type without import

`reveal_type` statements without importing them should work.

```python only=pyright
# revealed: Literal[1]
reveal_type(1)
```
