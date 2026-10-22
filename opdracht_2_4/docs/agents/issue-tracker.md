# Issue tracker: Azure DevOps Boards

Issues and PRDs for this repo live as Azure DevOps work items on the **Ops - BI** team board:
https://dev.azure.com/9altitudes-Internal/Internal%20projects/_boards/board/t/Ops%20-%20BI/Features

Use the `az boards` CLI (Azure CLI + `azure-devops` extension) for all operations.

## One-time setup

```
az extension add --name azure-devops
az devops configure --defaults organization=https://dev.azure.com/9altitudes-Internal project="Internal projects"
```

## Conventions

- **Create a work item**: `az boards work-item create --title "..." --type "Product Backlog Item" --area "Internal projects\Ops - BI" --description "..."`. Use `--type "Bug"`, `"Feature"`, or `"Task"` as appropriate for the work being tracked.
- **Read a work item**: `az boards work-item show --id <id>`.
- **List work items**: `az boards query --wiql "SELECT [System.Id], [System.Title], [System.State], [System.Tags] FROM WorkItems WHERE [System.TeamProject] = 'Internal projects' AND [System.AreaPath] = 'Internal projects\Ops - BI' AND [System.State] <> 'Closed'"` — adjust the WIQL `WHERE` clause for tag/state filters.
- **Comment on a work item**: `az boards work-item update --id <id> --discussion "..."`.
- **Apply / remove tags** (used as labels — see `docs/agents/triage-labels.md`): `az boards work-item update --id <id> --fields "System.Tags=tag1; tag2"` (this replaces the full tag list, so read current tags first and append/remove before writing back).
- **Close**: `az boards work-item update --id <id> --state Closed`.

## State automation (New → Active → Closed)

Agents drive the work item's `System.State` field directly instead of leaving it on `New` for the whole lifecycle:

- **On claim** (the moment an agent starts working a ticket — same trigger as the "Claim" step below): `az boards work-item update --id <id> --state Active --assigned-to <email>`.
- **On verified completion** (only after the fix/change has been validated — tests pass, PR merged, or the human/agent has confirmed the outcome; never close speculatively): `az boards work-item update --id <id> --state Closed --discussion "<summary of what was done / verification>"`.
- Do not skip `Active` — a ticket should visibly show it's in progress before it's closed, so the board reflects real-time status.

## Blocking relationships stay on the board after resolution

When a blocking work item is closed, the block link is a **permanent record**, not a temporary gate — never remove it. Instead:

1. Close the blocker: `az boards work-item update --id <blocker-id> --state Closed --discussion "<solution summary>"`.
2. Find every item it was blocking: `az boards work-item show --id <blocker-id>` (or a WIQL query) to list its `System.LinkTypes.Dependency-Forward` ("Successor"/"blocks") relations.
3. For each blocked item, post the resolution as a comment so the context travels with it: `az boards work-item update --id <blocked-id> --discussion "Unblocked by #<blocker-id>: <solution summary>"`.
4. Leave the `Predecessor/Successor` link in place on both items. "Is this still blocked?" is always answered by checking the **linked blocker's current state** (`Closed` = unblocked), never by whether the link still exists — this is what keeps the relationship visible on the board permanently.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

## When a skill says "publish to the issue tracker"

Create an Azure DevOps work item with `az boards work-item create`.

## When a skill says "fetch the relevant ticket"

Run `az boards work-item show --id <id>`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single work item with **child** work items as tickets.

- **Map**: a work item tagged `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body in its description.
- **Child ticket**: a work item linked to the map via a `Parent`/`Child` work item link (`az boards work-item relation add --id <child> --relation-type parent --target-id <map-id>`). Tag with `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, assign it to the driving dev (`az boards work-item update --id <id> --assigned-to <email>`).
- **Blocking**: Azure DevOps' native work item link type **"Predecessor/Successor"** (or "Blocked By" if enabled in the process). Add with `az boards work-item relation add --id <child> --relation-type "System.LinkTypes.Dependency-Reverse" --target-id <blocker-id>`. A ticket is unblocked when every blocker work item is `Closed` — the link itself is never removed once the blocker resolves; see "Blocking relationships stay on the board after resolution" above.
- **Frontier query**: query the map's open children via WIQL scoped to the map's parent link, drop any with an open (non-`Closed`) blocker link or an assignee; first in map order wins.
- **Claim**: `az boards work-item update --id <id> --state Active --assigned-to <email>` — the session's first write.
- **Resolve**: `az boards work-item update --id <id> --discussion "<answer>"`, then `az boards work-item update --id <id> --state Closed`, then propagate the resolution to any items this one was blocking (see above), then append a context pointer (gist + link) to the map's Decisions-so-far.
