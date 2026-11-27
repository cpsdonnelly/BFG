# Scenario extraction: agreements with the owner

Companion to `docs/BRIEFING_SCENARIO_EXTRACTION.md` (on the `claude/battlefleet-gothic-simulator-3sUkl`
branch until merged). Agreed with Ciarán, written by the extraction session working in
`cpsdonnelly/BFG-Scenarios`. If this conflicts with the briefing, ask Ciarán.

- **Where extraction happens.** In `cpsdonnelly/BFG-Scenarios` (zine PDFs, a content index, a
  scenario catalogue with XR conflicts). The extraction session copies finished bundles here as
  `scenarios/fanzine/<bundle>/<scenario>.md`.
- **Claims.** One file for all three stages: `docs/CLAIMS.md` in this repo, "Scenario bundles".
  `BFG-Scenarios` has no claims file of its own. Any bundle may be claimed, extraction included,
  by any collaborator's Claude Code session.
- **Which copy is authoritative.** Until a bundle merges here, the extraction copy in
  `BFG-Scenarios` is the master. After the merge, the copy in `scenarios/fanzine/` here is the
  master: fixes and "Owner ruling: ..." lines go in this repo only. Never edit both.
- **Scope.** Rules text, forces, set-up, special rules, victory conditions, ship stats. No art,
  no fluff, no whole articles. Non-profit; Battlefleet Gothic is no longer supported by Games
  Workshop.
- **Collaborators** get Write access to both repos from the owner, work on their own branch and
  never push to `main`. The owner approves merges. Pull requests are opened when the owner asks.
- **Catalogue.** `BFG-Scenarios/catalogue/scenarios.md` lists every scenario with the XR rules it
  depends on and conflicts with. Build sessions should read a scenario's entry there before
  building it.
