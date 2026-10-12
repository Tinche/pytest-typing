# Changelog

Versions follow [CalVer](https://calver.org) with a best-effort backwards-compatibility policy.

The **first number** of the version is the year.
The **second number** is incremented with each release, starting at 1 for each year.
The **third number** is when we need to start branches for older releases (only for emergencies).

## NEXT

- Run Pyrefly with the `default` preset so temporary snippets receive full type checking.
  Configure it with `typing_pyrefly_preset` or override it with `--typing-pyrefly-preset`.
  This requires a Pyrefly version supporting `--preset`; an empty preset omits the flag for older versions.
  ([#9](https://github.com/Tinche/pytest-typing/pull/9))

## 26.4.1 (2026-10-13)

- Update gh-action-pypi-publish to v1.14.2.
  ([#8](https://github.com/Tinche/pytest-typing/pull/8))
- Update build-and-inspect-python-package to v3.0.1.
  ([#7](https://github.com/Tinche/pytest-typing/pull/7))

## 26.4.0 (2026-10-12)

- Add Python 3.15 support.
  ([#6](https://github.com/Tinche/pytest-typing/pull/6))

## 26.3.0 (2026-03-24)

- Add Pyrefly support.
  ([#5](https://github.com/Tinche/pytest-typing/pull/5))

## 26.2.0 (2026-03-20)

- Add Pyright support.
  ([#3](https://github.com/Tinche/pytest-typing/pull/3))

## 26.1.0 (2026-03-17)

- Initial release.
