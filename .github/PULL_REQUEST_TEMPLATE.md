# Pull Request

## Summary

A concise description of what this PR changes and why.

## Related Issues

Closes #<!-- issue number -->

## Type of Change

- [ ] Bug fix (non-breaking — fixes an existing issue)
- [ ] New feature (non-breaking — adds new capability)
- [ ] Breaking change (existing behaviour changes)
- [ ] Documentation update
- [ ] Refactoring (no behaviour change)
- [ ] Test improvement
- [ ] Build / CI change

## Changes Made

List the key changes:

- 
- 
- 

## Testing

Describe how you tested this change:

```bash
# Commands used to verify the fix / feature
python -m pytest tests/ -v
python demos/pascal_like/run_pascal.py
```

- [ ] All 335 existing tests pass (`python -m pytest tests/ -q`)
- [ ] New tests added (if applicable)
- [ ] Tested on the affected backends / CLI commands

## Checklist

- [ ] Code follows the project style (line length ≤ 120, type annotations on public methods)
- [ ] Docstrings updated for any changed public classes or functions
- [ ] `docs/` updated if user-visible behaviour changed
- [ ] No new lint errors (`python -m pylint src/parsercraft/` or equivalent)
- [ ] `CHANGELOG.md` updated (if applicable)

## Screenshots / Output

If relevant, include before/after terminal output or screenshots.
