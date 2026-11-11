# frame-align

**English** | [简体中文](README.zh-CN.md)

> Align on the framework before you build.

`frame-align` is an agent skill for coding agents that can read and write files. Before any product code is written, the agent and the user go back and forth on an interactive HTML page until the user decides the framework of the idea holds. The agent restates what it understood in its own words, offers directions, points out gaps and contradictions, and locates the crux of hard problems. The user answers by clicking and leaving notes.

The skill is judged by one thing: whether the user reaches alignment with less effort than without it.

## Status

Early design draft.

- The skill instructions are written.
- The page is prebuilt, so it looks the same under every model. A small local server, bundled with the skill, serves it and saves each submission to a file that the agent reads on the next round.
- The page and both server scripts have been exercised with sample data in a browser. The skill as a whole has not been run through a complete alignment yet.

The skill instructions are written in Chinese. Pages follow the language the user writes in.

## Why

When a user brings a software idea, starting to build right away often produces something that both sides thought the other understood. The usual fix, a long list of clarifying questions, moves the work onto the user.

`frame-align` tries to avoid two failures at once:

- **Too heavy**: process and format box the agent in, different ideas get the same questions, and the agent's own insight never shows up.
- **Too light**: the agent skips alignment, or the page is just a normal answer in a different wrapper.

Its answer is to fix the shape of the loop and leave the content of the loop to the agent. Everything starts light and only gets heavier when lighter means have been tried.

## How it works

1. **Read before asking.** The agent reads whatever it can reach on its own, then restates the user's need in its own words.
2. **A round.** The agent explores and writes state to `.frame-align/state.js`. The prebuilt page shows it. The user clicks marks, writes notes, and submits; the page saves the result to `.frame-align/returns/round-N.txt`. The user says so in the conversation, the agent reads the file, adjusts, and writes the next round. The open page refreshes by itself.
3. **Exit.** The user decides when the framework holds. A short exit check lists what is still unresolved, then the agent writes a framework document, by default `framework/framework.md`.
4. **Rework.** The framework is not frozen at exit. When implementation exposes something the framework did not foresee, the skill is invoked again and picks up from the rework notes.

The skill covers the framework loop and rework. It does not manage implementation.

### On the page

- The user's own words stay pinned at the top as the goal. Only the user can change them.
- Content is sorted by what the user has to do: things that need your decision, things I am telling you, and small things I already decided for you. Each of the last kind can be taken back.
- Every card has marks that fit it and a note box. Marks cover the cheap decisions; notes carry what actually changes direction.
- A row of optional whole-round feedback: too much output, too little output, too hard to follow, off track, too slow, too fast.
- The page grows with the framework. The first page is the lightest one.
- The shell and the components are fixed: cards, comparison tables, numbered steps, a framework map as tiles or a tree, notes with SVG figures. Which of them appear, in what order and with what content is up to the agent, written as data. The agent never writes HTML.
- Results go to a file, not into the user's prompt. The conversation stays for what the user wants to say in their own words.

### Presets

A preset sets the direction of the first round, when the agent knows the least about the user. Its influence fades as feedback comes in.

| Preset | What the user brings | First round |
|---|---|---|
| Seed | One sentence, or a vague idea | Restate, offer a few directions. No challenges yet |
| Skeleton | An overall structure with many empty parts | Restate, draw the skeleton, mark the gaps |
| Checkup | A fairly complete draft | Restate, then point out the one or two most important contradictions or risks |
| Crux | A problem the user is stuck on | Restate, name the likely key point and why, propose the one check that best separates the possibilities. No experiment matrix |

### Keeping the decision with the user

The user agreeing with the agent is not a problem. The user no longer deciding is. This happens when output is too long to read, when a stream of professional-looking content gets waved through, or when the agent decides something the user never saw.

The skill treats this first as a problem with the agent's output: show less, separate what needs a decision from what does not, say things the user can judge. Only when lighter means fail does it ask the user to state their own leaning before seeing a recommendation.

It also asks the agent not to flatter and not to hedge: keep facts and opinions apart, re-check when challenged instead of yielding or insisting, give a clear recommendation, and verify rather than add disclaimers.

## Install

Copy the `frame-align/` folder into your agent's skills directory.

- **Claude Code**: `~/.claude/skills/frame-align/` for all projects, or `.claude/skills/frame-align/` inside one project. Invoke it with `/frame-align`.
- **Other agents that support Agent Skills**: use that agent's skills directory and its way of invoking a skill by name.

The page server needs Node.js or Python 3 on the machine. It has no other dependencies, listens on 127.0.0.1 only, and exits after twelve idle hours. Without either runtime the page can still be opened as a local file, with a save dialog or copy and paste as the way back.

The skill is meant to be invoked manually.

- `SKILL.md` carries `disable-model-invocation: true`, which Claude Code and Cursor honor. Remove that line before uploading the skill to claude.ai or packaging it for the Skills API, where unknown frontmatter fields are rejected.
- `agents/openai.yaml` sets `allow_implicit_invocation: false` for Codex. This follows the Codex documentation and has not been tested in Codex.
- Gemini CLI has no manual-only switch, so there the skill relies on the sentence in its description.

## Repository layout

```
frame-align/
  SKILL.md                      core loop
  references/
    state-format.md             state, log, observation notes, framework document
    page-contract.md            starting the page, composing it, marks, return file
    discipline.md               sources, re-checking, disputes, exit check
    lenses.md                   stack-neutral checklist of software framework angles
  assets/page.html              the prebuilt page
  scripts/serve.js              page server for Node.js
  scripts/serve.py              page server for Python 3
  agents/openai.yaml            manual-only invocation for Codex
```

## License

[MIT](LICENSE)
