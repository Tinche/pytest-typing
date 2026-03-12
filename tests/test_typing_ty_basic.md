# Tests for the Ty backend

These are tests that only run on Ty.

## Simple assignment

```python only=ty
a: int = 1
```

## Error message matching

In addition to matching on error codes, we can additionally match the exact error messages too.

```python only=ty
a: str = 1  # error: [invalid-assignment] Object of type `Literal[1]` is not assignable to `str`
```
