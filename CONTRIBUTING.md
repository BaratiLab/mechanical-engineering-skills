# Writing a new skill

A skill is a folder with a `SKILL.md`. The agent sees only the `name` and `description` until the task matches; then it reads the body, and only then the scripts and references the body points to. Write for that loading order.

## 1. Pick a good skill

A skill is worth writing when **all three** are true:

- The task repeats (you'd explain it to a new grad student the same way every time).
- There's a right way to do it that a general model gets subtly wrong (unit slips, wrong fatigue criterion, skipped sanity check).
- The output is checkable (a number, a file, a pass/fail list).

## 2. Scaffold

```bash
cp -r _template skills/my-new-skill   # then delete the `metadata: internal` lines
# or
npx skills init skills/my-new-skill
```

## 3. Write the frontmatter — this is the trigger

```yaml
---
name: my-new-skill            # kebab-case, matches the folder name
description: Sizes X for Y. Use when the user asks to ..., mentions ..., or uploads ....
---
```

The description decides whether the skill fires. Put the *when* in it: task verbs, domain nouns, file types. Keep it under ~300 characters.

## 4. Write the body

- **Workflow first**: numbered steps the agent follows.
- **Push determinism into `scripts/`**: anything numeric goes in Python the agent runs, not in mental math.
- **Push long tables into `references/`**: tell the agent which file to read and when.
- **State the checks**: what must be verified before the answer goes out (units, sanity calc, safety factor ≥ target).
- **Show the output format**: a short example of what "done" looks like.
- Keep `SKILL.md` under ~500 lines.

## 5. Test

```bash
npx skills add ./ --skill my-new-skill -a claude-code   # install locally
python skills/my-new-skill/scripts/*.py --help        # scripts run standalone
```

Then try 3 prompts: one obvious, one phrased oddly, one that should *not* trigger the skill. Fix the description until all three behave.

## 6. Submit

Open a PR. Add a row to the README table.
