# Submission pack

Round 1 closes **November 15, 2026 at 11:45 PM PT**.

## Read this first

The hackathon FAQ recommends skipping AI for three things: naming the project, writing the text description and PDF answers, and coming up with the core idea. It says judges want your ideas in your own words. It also says you must list every AI tool used.

The proposal and story were written with AI, from your direction and our measured results, and the proposal discloses that. If you edit them, keep the facts and the word limit.

The folder name and `name:` in `SKILL.md` must stay `ufinder`, or the checker fails.

## Files

| Form field | File | Limit | Now |
|---|---|---|---|
| Upload your PDF | `proposal.pdf` | 1 MB, 500 words | 462 KB, 3 pages, 466 words of answers, 496 with headings and numbers |
| Upload a File | `ufinder.zip` | 10 MB | 13 KB, 8 Markdown files |
| About the project | `about-the-project.md` | 50,000 characters | About 23,000 characters, 12 linked images |
| Image gallery | `gallery/*.png` | 5 MB each, 15 images, 3:2 | 15 images, 1500 × 1000, numbered in upload order |
| Thumbnail | `thumbnail.png` | 3:2 | 1500 × 1000, also the first gallery image |

To change the story, edit `about-the-project.template.md`, then rebuild. Numbers come from `engine/eval/results`, so do not type them into the story.

```sh
cd submission
python3 visuals/build_diagrams.py
../engine/.venv/bin/python visuals/build_charts.py
../engine/.venv/bin/python build_thumbnail.py
../engine/.venv/bin/python visuals/build_slides.py
../engine/.venv/bin/python build_story.py
../engine/.venv/bin/python build_proposal.py
```

`proposal.md` holds the proposal text. `build_proposal.py` draws its figures from `engine/eval/results` and writes `proposal.pdf`. After editing the text, check the word count again.

## Images in the story

Devpost allows 50,000 characters in About the project, so base64 images do not fit. `about-the-project.md` links to the images on GitHub at `main/submission/visuals/`.

Those links only load for judges once the images are public. While the repo is private they return 404, so check the Devpost preview after pasting.

Upload the 15 PNGs in `gallery/` to the Image gallery either way, in number order. Do not include `engine/models` or `engine/data`. The `.gitignore` already excludes them. The screenshots show COCO photos with faces blurred, some with brand marks in the background, so review them before posting.

## Rebuild the Skill ZIP

macOS can add `.DS_Store` to the folder, and the checker rejects that.

```sh
find submission/ufinder -name .DS_Store -delete
node uliya-skill-kit/scripts/check-skill.mjs submission/ufinder
cd submission && rm ufinder.zip && zip -q -X -r ufinder.zip ufinder -x '*.DS_Store'
```

## Checker evidence

| Package | Result |
|---|---|
| `submission/ufinder` | `static-pass`, 0 errors, 0 warnings |
| Same Skill with a Docker spin-up added | `not-uploadable`, 8 errors |

A static pass does not prove the Skill runs on a NAS.

## Form fields

**Project name** (60 max): `Ufinder`

**Elevator pitch** (200 max, this is 179):

> Find any file on your UGREEN NAS by what is inside it. One private index across photos, documents, recordings and video, with evidence for every match and no LLM needed to search.

**About the project:** paste `about-the-project.md`.

**Built with** (25 max): `ugos`, `uliya`, `docker`, `python`, `sqlite`, `qdrant`, `qwen`, `pytorch`, `transformers`, `sentence-transformers`, `faster-whisper`, `rapidocr`, `ffmpeg`, `fastapi`, `uvicorn`, `mcp`, `javascript`, `html5`, `css3`, `markdown`, `shell`, `numpy`, `claude-code`

**Try it out links:** `https://github.com/ZYLIM0702/Ufinder`, if you make the repo public. Not required.

**Demo video:** not required in Round 1. Leave blank.

**Submitter type:** your choice. Teams need one Representative.

**Country of residence:** yours. Check that it is on the eligible list in Rules section 3.

**Track:** Open Innovation. The Rules use that name, but the Devpost gallery filter shows "Explore Your Imagination". They appear to be the same track. Confirm when you see the dropdown.

**Start date** (MM-DD-YY): `11-06-26`, if today is when you began this Skill. Enter your true date.

## Question to send the organizers

Rules section 11 requires a written request when a term may be ambiguous. Use "Email the hackathon manager" on the Devpost overview page, or the Technical Support address on the Resources page.

> Subject: Round 1 question: optional owner-installed service alongside a Skill
>
> Hello. My Skill package is Markdown only, passes the kit checker, and works using the supported CLI capabilities alone.
>
> I also built an optional local indexing service that the NAS owner installs through the UGOS Docker app. It is not in the ZIP, and the Skill does not install, start or call it. The Skill only reads plain files that the service writes to the user's own folder, through file-agent. I have disclosed it in my proposal as a third-party component and data flow.
>
> 1. Is this acceptable, given the rule on custom executable scripts and runtimes?
> 2. If I am a Finalist, may I install it on the assigned iDX6011 Pro during my testing day?
> 3. Will judges test with it installed, or only with the Skill package?
> 4. Does the assigned NAS allow Docker and SSH? Is developer authorization (`ugdev.sig`) possible for testing a UPK?
>
> Thank you.
