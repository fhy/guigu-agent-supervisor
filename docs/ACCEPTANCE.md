# T001 Acceptance

## Functional matrix

- valid mock request starts one named tmux session and returns a run ID;
- status distinguishes running, completed, failed, cancelled and stopped;
- a valid result is returned unchanged through `result`;
- missing and malformed results return fixed errors;
- graceful stop and forced fallback affect only the owned session;
- repeated stop is idempotent;
- duplicate active worktree start is rejected;
- a terminal run releases worktree ownership;
- two different worktrees may run independently;
- timeout produces a fixed terminal classification;
- stale tmux disappearance is classified without claiming success;
- restart of the CLI can inspect an existing run from files and tmux state.

## Security matrix

- reject relative worktree and prompt paths;
- reject paths outside approved roots;
- reject prompt symlink, directory and oversized file;
- reject unknown backend, role, result type and JSON field;
- prove arguments containing shell metacharacters are not executed;
- prove an unowned tmux session is unchanged by stop;
- prove status/errors do not contain prompt text or planted environment sentinels;
- prove state files are created with user-only permissions.

## Quality gates

- formatter and static checks selected by the implementation language pass;
- unit tests cover schema/path/state functions;
- process tests use real tmux and the mock backend;
- test artifacts are confined to a temporary root;
- README usage matches the implemented CLI;
- implementation handoff names the exact commit, changed files, tests, limitations and
  next recommended experiment.
