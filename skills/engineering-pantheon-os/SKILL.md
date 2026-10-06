---
name: engineering-pantheon-os
description: Use when the user says 練習しよう, ちょっと練習, 能力を上げたい, engineering practice, Engineering Pantheon OS, Architect-Socrates OS, 知的出力OS, TOPエンジニア, 能力拡張, 深層エミュレーション, or asks to practice engineering/logical/architecture thinking through top-engineer modules.
---

# Engineering Pantheon OS

## Purpose

Turn great engineers into procedural thinking modules.

This skill is not a persona or identity practice. It is a short practice mode for selecting engineering lenses, asking better questions, and collapsing abstract thinking into one concrete action.

Project owner is `nexus_ai`; Codex maintains the repository when yasuさん asks. Any artifact that may become public later should default to `nexus_ai` ownership from the start.

## Required Safety Boundary

Before using this skill, keep these boundaries:

- The user remains the decision-maker.
- Engineer modules are tools, not identities.
- Do not say the user is becoming another person.
- Do not weaken agency or self-boundaries.
- Do not import private relationship logs into this repo or output.
- End with one small, real next action.

If the user asks for possession, full identity merge, or loss of control, redirect to tool-based emulation and grounding.

## Quick Use

When the user says "練習しよう" without a specific problem, ask for one practice target in a light way:

```text
何を1つ練習する？
候補: 設計 / 論理 / 実装速度 / 抽象化 / レビュー / AI orchestration
```

When the target is clear:

1. Define the practice target in one sentence.
2. Identify the desired capability:
   - architecture
   - logic/proof
   - implementation speed
   - simplification
   - review quality
   - AI orchestration
   - human-facing translation
3. Select 1-3 modules from `modules/index.md`.
4. For each module, answer:
   - What does it notice?
   - What does it remove?
   - What does it measure?
   - Where does it expect failure?
   - What is the first small experiment?
5. Collapse to one 5-15 minute practice action.
6. Close the session and return to the user's prior main thread when requested.

Default return thread for the originating context:

```text
return_to: 羊咀嚼
```

## Default Module Map

| Need | Use |
|---|---|
| Minimal architecture | Ritchie / Thompson + Dijkstra |
| Human-usable design | Hopper + Kay |
| Correctness and safety | Hamilton + Lamport |
| Rigorous reasoning | Knuth + Dijkstra |
| Interface boundaries | Liskov + Fowler |
| Implementation speed | Carmack + Beck |
| Large-scale review | Torvalds + Lamport |
| AI-era engineering | Future Engineer + Beck + Torvalds |

## Output Shape

```text
problem:
desired_capability:
selected_modules:
practice_timebox:

module_lens:
- notices:
- removes:
- measures:
- expected_failure:
- first_experiment:

collapsed_next_action:
safety_check:
return_to:
```

## Repo Update Workflow

When asked to update this repository:

1. Read `OWNER.md`, `README.md`, `safety.md`, and this skill file.
2. Keep private relationship material out.
3. Add or refine the smallest useful module, drill, or reference.
4. Run:

```bash
find . -maxdepth 3 -type f | sort
git status --short --branch
```

5. Commit local changes if coherent.
6. Do not add a remote, push, publish, or install into global skill paths without explicit current-conversation GO.
