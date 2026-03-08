python := ""
covcleanup := "true"

# Sync the environment, to a particular version if provided. The `python` variable takes precedence over the argument.
sync version="":
    uv sync {{ if python != '' { '-p ' + python } else if version != '' { '-p ' + version } else  { '' } }} --all-groups

typecheck:
    uv run -p python3.14 --group lint mypy src/ tests

[parallel]
lint: typecheck
    uv run -p python3.14 --group lint ruff check src/ tests
    uv run -p python3.14 --group lint ruff format --check src tests

fix:
    uv run -p python3.14 --group lint ruff check --fix src/ tests
    uv run -p python3.14 --group lint ruff format src tests

test *args="-x --ff tests":
    uv run {{ if python != '' { '-p ' + python } else { '' } }} --group test --group lint pytest {{args}}

testall:
    just python=python3.10 test
    just python=pypy3.10 test
    just python=python3.11 test
    just python=python3.12 test
    just python=python3.13 test
    just python=python3.14 test

cov *args="-x --ff tests":
    uv run {{ if python != '' { '-p ' + python } else { '' } }} --group test --group lint coverage run -m pytest {{args}}
    {{ if covcleanup == "true" { "uv run coverage combine" } else { "" } }}
    {{ if covcleanup == "true" { "uv run coverage report" } else { "" } }}
    {{ if covcleanup == "true" { "@rm .coverage*" } else { "" } }}

covall:
    just python=python3.10 covcleanup=false cov
    just python=pypy3.10 covcleanup=false cov
    just python=python3.11 covcleanup=false cov
    just python=python3.12 covcleanup=false cov
    just python=python3.13 covcleanup=false cov
    just python=python3.14 covcleanup=false cov
    uv run coverage combine
    uv run coverage report
    @rm .coverage*
