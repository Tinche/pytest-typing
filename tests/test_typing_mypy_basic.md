# Tests for the Mypy backend

These are tests that only run on Mypy.

## Simple assignment

```python only=mypy
a: int = 1
```

## Error message matching

In addition to matching on error codes, we can additionally match the exact error messages too.

```python only=mypy
a: str = 1  # error: [assignment] Incompatible types in assignment (expression has type "int", variable has type "str")
```
