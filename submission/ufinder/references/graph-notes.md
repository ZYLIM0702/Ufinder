# Graph notes

Map mode writes plain Markdown notes that link to each other. This gives a folder a small file graph on a stock NAS, with no extra software. Later searches can read these notes through the normal evidence services.

## One note per mapped file

Use this shape. Values must come from real results.

    ---
    ufinder_id: stable short name derived from the file name
    source_path: real path
    type: photo | document | recording | video | other
    modified: real modified time
    tags: [real tags only]
    ---

    # File title

    Summary: one sentence from the real result.

    ## People and subjects

    [[Subject name]]

    ## Related

    - [[Other note]]: same subject, because the shared evidence is named here

## Hub notes

If two or more mapped files share a real subject, person, organisation or project, create one short note for it. Those hub notes connect the graph, because the links point to them.

## Rules

- Link only notes that exist in this run or were listed in the destination folder.
- If a file names another file that is not on the NAS, list it under a heading called Missing, with the file that mentioned it.
- State the evidence for each Related link.
- Keep notes short. Do not copy whole documents into a note.
- Do not include credentials or personal ID numbers in a note. Report that they were left out.
