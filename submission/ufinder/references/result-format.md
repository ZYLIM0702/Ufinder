# Result format

## Merge

Merge by real path. If two results point to the same path, keep one row and combine the evidence.

## Rank

Rank by evidence, not by model opinion:

1. Confirmed: a content check agreed, such as a `yes` verdict from the vision check or a matching quoted passage.
2. Strong: two or more independent signals agree, such as OCR text and a scene match.
3. Possible: one signal only.
4. Name only: file name, path or date matched, and the content was not checked.

Inside a group, keep the order each service returned. Do not make up scores.

## Output

Show up to 10 rows, then say how many more exist.

| Field | Content |
|---|---|
| File | real path |
| Type | photo, document, recording, video, other |
| Match | Confirmed, Strong, Possible, Name only |
| Why | the signals, such as OCR text, passage or page, transcript segment, vision verdict |
| Evidence | one short quote or reason, taken from the real result |

After the rows, add:

- Searched: services and scope that ran
- Not covered: services that failed, were skipped, or reported partial coverage
- Next: album, tag, save as note, or show related files

## Relate labels

Use only labels backed by a real result: `same content` (duplicate), `same tag`, `same subject`, `same folder`, `same time`. If no link has evidence, say so.
