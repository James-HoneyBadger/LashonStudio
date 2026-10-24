---
name: Bug report
about: Report a defect in Lashon
title: '[BUG] '
labels: bug
assignees: ''
---

## Describe the Bug

A clear and concise description of what the bug is.

## Steps to Reproduce

```python
# Minimal reproducible example — please include:
# 1. The grammar or config used
# 2. The source code being parsed
# 3. The code that triggers the bug

from lashon.parser import GrammarParser, PEGInterpreter

grammar = GrammarParser().parse("""
    # ... your grammar here ...
""")

ast = PEGInterpreter(grammar).parse("... your source ...")
```

## Expected Behaviour

What you expected to happen.

## Actual Behaviour

What actually happened. Include the full traceback if an exception was raised:

```
Traceback (most recent call last):
  ...
```

## Environment

| Item | Value |
|---|---|
| Lashon version | (run `lashon --version`) |
| Python version | (run `python --version`) |
| Operating system | (e.g. Ubuntu 22.04, macOS 14, Windows 11) |
| Install method | `pip install -e .` / `pip install lashon` |

## Additional Context

Any other details, screenshots, or related issues that might help diagnose the problem.
