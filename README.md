# frame-align

**English** | [简体中文](README.zh-CN.md)

> Align on the framework before you build.

`frame-align` is an agent skill for coding agents that can read and write files. Before any product code is written, the agent and the user go back and forth on an interactive HTML page until the user decides the framework of the idea holds. The agent restates what it understood in its own words, offers directions, points out gaps and contradictions, and locates the crux of hard problems. The user answers by clicking and leaving notes.

The skill is judged by one thing: whether the user reaches alignment with less effort than without it.

## Status

Early design draft.

- The skill instructions are written.
- The page is prebuilt, so it looks the same under every model. A small local server, bundled with the skill, runs once per round: it opens the page, waits for you to submit, hands the submission to the agent, and exits. No process is left running between rounds.
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
2. **A round.** The agent explores, writes state to `.frame-align/state.js`, and runs the page command, which opens the page in the browser. The user clicks marks, writes notes, and submits. The result is saved to `.frame-align/returns/round-N.txt` and handed straight to the waiting agent, which adjusts and writes the next round. The open page refreshes by itself. The agent waits a few minutes at most; a user who submits later says so in the conversation, and the page then delivers the result by itself.
3. **Exit.** The user decides when the framework holds. A short exit check lists what is still unresolved, then the agent writes a framework document, by default `framework/framework.md`.
4. **Rework.** The framework is not frozen at exit. When implementation exposes something the framework did not foresee, the skill is invoked again and picks up from the rework notes.

The skill covers the framework loop and rework. It does not manage implementation.

### On the page

- The user's own words stay pinned at the top as the goal. Only the user can change them.
- Content is sorted by what the user has to do: things that need your decision, things I am telling you, and small things I already decided for you. Each of the last kind can be taken back.
- Every card has marks that fit it and a note box. Marks cover the cheap decisions; notes carry what actually changes direction.
- A row of optional whole-round feedback: too much output, too little output, too hard to follow, off track, too slow, too fast.
- The page grows with the framework. The first page is the lightest one.
- The shell and the components are fixed: cards, comparison tables, numbered steps, a framework map as tiles or a tree, notes. Which of them appear, in what order and with what content is up to the agent, written as data. The agent does not write the page.
- The agent can draw. A card, a note or a framework part can carry a figure: an SVG, or a fragment of HTML with its own styles and scripts. Figures are isolated from the page, so whatever a model draws cannot break or read it, and they are shown on light paper in both themes. Text fields also take code blocks for ASCII diagrams and trees.
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

## Using the page

The page opens in your browser by itself. Respond to what you care about and press **Submit**. Nothing is required: anything you leave untouched simply means you have no opinion on it yet.

### Top of the page

| Control | What it does |
|---|---|
| **Your goal** · Edit | Your own words, pinned as the goal. Press Edit to rewrite it, then Done. Only you can change it. |
| The tinted line under the goal | What the agent read from your last round, what it changed, and what this round is for. Read only. |
| **What I understood** · Edit it where it is wrong | The agent's restatement of your need. Rewrite it directly if it is off. When nothing changed since last round it is folded into one line you can open. |
| **Your background** | First round only, optional. Click the experience chips that apply, or type a line. |

### Cards

Every card has a note box. Type anything there: a reason, a correction, a condition. Text boxes grow with what you type, so long text stays fully visible. Marks handle the cheap decisions; notes are where direction changes.

| Card | Controls | Effect |
|---|---|---|
| A decision for you | Click an option block, or **Choose** under a column of the comparison table. Click again to clear. The recommended option carries a badge, with the reason below. | The matching part of the framework becomes confirmed. |
| An idea | **Keep**, **Drop**, **More like this** | Keep makes it a candidate part of the framework. More like this steers the next round in that direction. |
| A suggestion | **Accept**, **Reject** | Accept merges it into the framework. Reject leaves it out and is logged. |
| A fact, shown with its source | **Not right** | The agent re-checks and reports what it found. |
| An explanation | **Still unclear** | The agent explains again in a different way. |
| Most cards | **Explain**, **Verify** | Explain asks for the reasoning. Verify tells the agent this point matters and it should check its basis. |

Accept and Reject exclude each other, as do Keep and Drop. Other marks can be combined. Long detail text is partly folded; **Show more** opens it.

### Other areas

| Control | What it does |
|---|---|
| **N more not expanded** | Lower-priority items the agent held back. Open it if you want them. Whether you opened it is recorded, so the agent learns how much you want to see. |
| **Already decided for you** · I will decide | Small things the agent settled on its own. Press I will decide on any of them to take it back; it returns next round as a decision for you. |
| **Framework so far** | A bar showing how many parts are confirmed, open or disputed, then one tile per part. Click a tile to read it and leave a note. **Reopen** turns a confirmed part back to open. A "Basis changed" flag means a file it relied on has changed. |
| **How was this round overall** | Six optional chips: too much output, too little output, too hard to follow, off track, too slow, too fast. The agent adjusts the next round accordingly. |
| The large text box | Anything not covered above: questions, complaints, a different direction. |
| **Next** | Another round continues. Enough ideas tells the agent to stop offering directions and start filling in and narrowing down. Framework holds starts the exit check. |
| **Notes about you** | What the agent has observed about how you work, which it uses to adjust what it shows. Edit anything that is wrong. |

### Submitting

- **Submit** saves your responses to `.frame-align/returns/round-N.txt` and hands them to the agent. When the bar at the bottom says "Delivered", the agent is already carrying on and you do not need to go back to the conversation. You can still add anything there at any time.
- When the bar says "Filled in, not delivered yet", the agent has stopped waiting, usually because you took a while. Say so in the conversation and the page delivers the result by itself. You do not have to press Submit again.
- While the agent is not waiting, the page can still be read and filled in.
- The rest of the time the bar shows how many cards you have responded to.
- After you submit, leave the page open. It refreshes by itself when the next round is ready.
- What you fill in is kept in the browser until the round changes, so a reload does not lose it.
- **Manual copy (fallback)** at the very bottom is only for the case where saving fails.

## Install

Copy the `frame-align/` folder into your agent's skills directory.

- **Claude Code**: `~/.claude/skills/frame-align/` for all projects, or `.claude/skills/frame-align/` inside one project. Invoke it with `/frame-align`.
- **Other agents that support Agent Skills**: use that agent's skills directory and its way of invoking a skill by name.

The page server needs Node.js or Python 3 on the machine and has no other dependencies. It does not stay running: it runs only for the round in which the agent is waiting for you, exits as soon as you submit, and exits by itself after nine minutes at most. It listens on 127.0.0.1 only, hands the state only to the page it served itself, and accepts submissions only from that page. A project keeps the same address every time, recorded in `.frame-align/server.json`. Without either runtime the page can still be opened as a local file, with a save dialog or copy and paste as the way back.

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
    page-contract.md            running the page, composing it, marks, the return
    discipline.md               sources, re-checking, disputes, exit check
    lenses.md                   stack-neutral checklist of software framework angles
  assets/page.html              the prebuilt page
  scripts/serve.js              page server for Node.js
  scripts/serve.py              page server for Python 3
  agents/openai.yaml            manual-only invocation for Codex
```

## License

[MIT](LICENSE)
