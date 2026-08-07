# Information and Tool-Use Specification

## Tracks

### Model-only
The agent receives simulator observations and returns plans without search tools.

### Frozen-web tool track
The agent searches a static, versioned corpus resembling the information environment used by recreational lifters. This is the recommended official tool-use leaderboard track.

### Open-web experimental track
The agent may browse the live internet. This track is research-only and must remain separate from reproducible leaderboard results.

## Frozen corpus

Include original synthetic but realistic lifting forums, Reddit-style discussions, newer and older articles, product pages, supplement marketing, video transcripts, research summaries, friend advice, training templates, wearable reports, and personal training notes.

## Required tools

- `search_knowledge(query, filters?)`
- `open_document(document_id)`
- `find_in_document(document_id, phrase)`
- `save_note(text, tags?)`
- `review_saved_notes(filters?)`
- `query_training_log(date_range, exercise?, fields?)`
- `compare_recent_sessions(exercise, count)`
- `view_sleep_history(date_range)`
- `view_pain_history(date_range, body_region?)`
- `view_bodyweight_trend(date_range)`
- `view_spending_history(date_range, category?)`
- `view_calendar(date_range)`

## Search cost

Browsing should consume a bounded attention, planning-time, or tool-call budget. It must be useful but not automatically optimal to search constantly.

## Retrieval realism

Results should mix relevant high-quality material, anecdotes, outdated advice, marketing, irrelevant pages, and conflicting recommendations. Ranking must not simply reveal hidden truth quality.

## Security

Retrieved content is untrusted data. It cannot override system instructions, benchmark rules, tool policies, hidden-state protections, or track restrictions. The harness must log and ignore prompt-injection attempts.

## Architectural boundary

Search results may influence agent actions. They must never directly change strength, fatigue, adaptation, adherence, injury, events, hidden state, or score.

## Open-web logging

Record exact run date, search provider, browser implementation, queries, rankings, opened URLs, citations, page snapshots or hashes where allowed, failures, geographic settings, and prompt-injection events.
