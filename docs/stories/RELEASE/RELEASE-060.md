---
id: RELEASE-060
rail: RELEASE
title: Post-fold re-sync of migrated projects + RELEASE-002 status reconciliation
status: draft
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.
---

## Context

`/mnt/work/flex-harness` is the **permanent release channel** (see
`docs/architecture.md` § *Release channel — flex-harness*), not a temporary
worktree slated for removal. This story's re-sync work is performed *from*
that permanent channel, not as a one-time step ahead of tearing it down.
RELEASE-061 (*"Worktree and branch retirement — remove
/mnt/work/flex-harness"*) is **superseded** and will never be built — see its
`## Superseded` section — so any step below that only made sense ahead of a
worktree/branch removal has been dropped or restated accordingly.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->

## Instructions

## Tests
