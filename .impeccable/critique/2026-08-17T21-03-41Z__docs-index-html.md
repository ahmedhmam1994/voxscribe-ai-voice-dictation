---
target: VoxScribe landing page (docs/index.html)
total_score: 24
max_score: 36
na_heuristics: 7
p0_count: 0
p1_count: 2
timestamp: 2026-08-17T21-03-41Z
slug: docs-index-html
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2/4 | No active-section nav indicator; mockup's live-looking states are illustrative only |
| 2 | Match Between System & Real World | 3/4 | Plain-English copy reads naturally; icon glyphs more abstract than the text |
| 3 | User Control and Freedom | 3/4 | Simple scroll, anchor nav, nothing traps the user |
| 4 | Consistency and Standards | 2/4 | Recording state shown in green, conflicting with the near-universal red = "recording" convention; mismatched icon set |
| 5 | Error Prevention | 3/4 | SmartScreen warning explained proactively, before the user hits it |
| 6 | Recognition Rather Than Recall | 3/4 | Comparison table + FAQ keep everything visible |
| 7 | Flexibility and Efficiency | n/a | Static Persuade-mode page, no repeat-use shortcuts apply |
| 8 | Aesthetic and Minimalist Design | 2/4 | Generic dark-SaaS polish undercut by mismatched icons and an overloaded 6-item grid |
| 9 | Error Recovery | 3/4 | SmartScreen guidance is clear and actionable, if repetitive |
| 10 | Help and Documentation | 3/4 | GitHub/Releases/Issues + FAQ give a real support path |
| **Total** | | **24/36** | **Acceptable (67%)** |

## Design Specificity Verdict

LLM assessment: recognizable "indie dark SaaS" template -- sticky blurred nav, purple gradient accent, eyebrow badge, gradient-text hero, 3-column icon-card grid, 3-step flow, comparison table, FAQ. Swap the copy and this exact DOM/CSS could sell a password manager unchanged. The violet accent has no inherent tie to voice/audio/local-first. What is specific is the copy: clipboard-avoidance details, Bluetooth mic sample-rate FAQ, SmartScreen explanation -- clearly written by someone who knows this app's real internals. The words are authored for VoxScribe; the visual system is not.

Deterministic scan: 4 confirmed findings, zero false positives -- gradient-text (line 64), dark-glow (line 100, .status-dot #3ecf8e), em-dash-overuse (15, grep-confirmed), aphoristic-cadence (3+ "No X, no Y" constructions).

Convergence: detector's dark-glow hit on .status-dot independently corroborates the design review's P2 finding that recording state uses green instead of red -- two independent methods flagged the same element. Detector-only catch: em-dash and aphoristic-cadence copy patterns, which the design review (focused on UX/visual structure) did not evaluate.

Visual overlays: no live in-browser overlay injected (no mutable browser session available); static screenshots captured instead at .impeccable/critique-evidence/desktop.png and mobile.png as fallback evidence.

## Overall Impression

Bones are sound -- clear IA, a real value proposition, copy grounded in actual implementation details. Visual execution is the generic "AI-generated default" look: generic violet/dark palette, a fake CSS mockup standing in for real product proof, a recording-state color that contradicts a universal convention. Highest-leverage fix: replace the illustrated mockup with real product evidence.

## What's Working

- The SmartScreen reassurance block -- names the exact dialog text, tells the user precisely what to click, explains why. Highest-leverage UX on the page.
- The comparison table -- turns an abstract value prop into four skimmable yes/no rows.
- Implementation-grounded feature copy -- "clipboard contents are never touched" is specific and credible, not generic marketing-speak.

## Priority Issues

[P1] No real product proof, only an illustration. The hero mockup is a hand-built CSS fake, not an actual screenshot/recording. Fix: replace with a real looping GIF/WebP of the actual app in use. Suggested command: $impeccable polish.

[P1] Feature grid overloads the chunking limit. 6 equally-weighted cards violate the <=4-items-per-group cognitive load rule, burying the two real differentiators. Fix: cut to 3-4 strongest differentiators; fold the rest into How It Works. Suggested command: $impeccable distill.

[P2] Recording state uses green, not red. Confirmed by both assessments independently. Breaks the universal red = "mic is hot" convention. Fix: red or pulsing-amber for recording state; reserve green for success/ready. Suggested command: $impeccable colorize.

[P2] SmartScreen warning explained twice, near-verbatim, right before the download decision. Fix: one authoritative explanation in Install; FAQ links/anchors to it instead of repeating. Suggested command: $impeccable clarify.

[P3] No focus-visible styling anywhere. Keyboard users get zero confirmation of focus position. Fix: add a visible focus ring to all interactive elements. Suggested command: $impeccable audit.

## Persona Red Flags

Jordan (confused first-timer): two different "recording" UI representations appear at once (mockup status/button vs. floating pill) with nothing clarifying they're the same feature at different moments. Hits the bolded amber SmartScreen warning cold.

Riley (stress tester): no OS-gating on Download for Windows 7/8 visitors. "v1.0" reads like a changelog link but is dead text. No failure-mode language for mis-transcription or an interrupted first-launch model download.

Casey (distracted mobile user): at max-width 760px, nav .links{display:none} removes all in-page navigation with no hamburger replacement. Comparison table has no overflow-x:auto wrapper for narrow viewports.

## Minor Observations

- "v1.0" in hero fine print isn't a link to release notes
- Eyebrow badge and fine print below it repeat the same facts almost verbatim within one screen
- Primary CTA uses an emoji arrow, secondary CTA doesn't -- inconsistent treatment
- Feature-card icons are a mismatched grab-bag of Unicode symbols, not one coherent icon family
- Page closes on a legal-disclaimer line rather than a reinforcing CTA
- 15 em-dashes, 3+ "No X, no Y" constructions (detector-confirmed) -- worth a copy pass

## Questions to Consider

- What if the hero mockup were a real muted looping screen recording -- would that single swap outperform every copy edit here?
- What if the comparison table named real competitors instead of "typical cloud dictation tools"?
- What if the SmartScreen section showed an actual annotated screenshot of the real dialog instead of two prose explanations?
