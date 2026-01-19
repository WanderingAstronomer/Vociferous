# Agent Research Journal - History Title Affordance & Truncation

## Task Overview
The goal was to improve the affordance in History and Project views by dynamically adjusting title truncation. 
Previous behavior: Titles were hard truncated at 30 characters regardless of view width, leaving "significant room" unused on wide displays. Visual truncation by Qt was character-based, potentially cutting words mid-stream.

## System Understanding and Assumptions
- **Data Layer**: `TranscriptionModel` generates the display text for fallback titles (when no custom title exists). It used a hardcoded `max_length=30` and `format_preview`.
- **Presentation Layer**: `HistoryTreeView` uses `TreeHoverDelegate` to paint the items. It used `fontMetrics.elidedText` with `ElideRight`, which is efficient but character-based.
- **Requirement**: 
  1. Increase data length to allow dynamic sizing.
  2. Implement "word-aware" elision (ellipses after the nearest previous word) to avoid mid-word cuts.

## Decisions Made
1.  **Increased Data Limit**: Bumped `max_length` in `TranscriptionModel` from 30 to 120 characters. This acts as the "upper bound" for the fallback title. 120 characters is enough to fill a standard history view width on large monitors without being excessive.
2.  **Word-Aware Data Truncation**: Modified `src/ui/utils/history_utils.py` `format_preview` to respect word boundaries when generating the fallback string itself.
3.  **Word-Aware Visual Elision**: Implemented `_elide_word_aware` in `TreeHoverDelegate`.
    - It first uses Qt's efficient `elidedText`.
    - If truncation occurred, it checks if the cut was mid-word (by checking the next char in original text).
    - If mid-word, it backtracks to the previous space and re-appends the ellipsis (`…`).
    - This ensures titles like "The quick brown fox" truncate to "The quick brown…" instead of "The quick bro…".

## Trade-offs Considered
- **Performance**: Word-aware elision adds a small overhead (string slicing, finding last space) on top of Qt's elision. Since text length is capped at 120 chars, this is negligible even for rapid repaints.
- **Complexity**: Added custom drawing logic vs just using Qt's `ElideRight`. The custom logic is necessary to meet the "avoid cutting off words mid-stream" requirement.

## Post-Task Recommendation
The changes directly address the user's "dynamic sizing" and "affordance" request. This journal should be archived.
