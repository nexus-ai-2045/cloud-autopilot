# Pantheon Practice Boot

Use this when saying "練習しよう" and selecting modules for a short practice session.

Default timebox: 5-15 minutes.

```text
practice_target:
desired_capability:
selected_modules:
practice_timebox:

module_1:
- notices:
- removes:
- measures:
- expected_failure:
- first_experiment:

module_2:
- notices:
- removes:
- measures:
- expected_failure:
- first_experiment:

collapsed_next_action:
return_to:
```

## Selection Rules

- Use 1 module for small decisions.
- Use 2-3 modules for architecture or reasoning problems.
- Do not use more than 3 modules in one pass.
- If the output is abstract, rerun with a smaller problem.
- Close by naming the next tiny action and the return thread.

## Default Return

```text
return_to: 羊咀嚼
```
