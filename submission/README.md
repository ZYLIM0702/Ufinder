# Submission pack

Round 1 closes **November 15, 2026 at 11:45 PM PT**.

## Read this first

The hackathon FAQ recommends skipping AI for three things: naming the project, writing the text description and PDF answers, and coming up with the core idea. It says judges want your ideas in your own words. It also says you must list every AI tool used.

So the proposal and story are **drafts built from what you wrote and what we measured**. Rewrite them in your own voice before submitting. Keep the facts and the word limit.

`Ufinder` is a working name. If you rename it, the folder name and `name:` in `SKILL.md` must match, or the checker fails.

## Files

| Form field | File | Limit | Now |
|---|---|---|---|
| Upload your PDF | `proposal.pdf` | 1 MB, 500 words | 6 KB, 468 words of answers, 497 on page 1 with labels |
| Upload a File | `ufinder.zip` | 10 MB | 9 KB, 6 Markdown files |
| About the project | `about-the-project.md` | No limit | 3,200 words, 12 images |
| Image gallery | `visuals/*.png` | 5 MB each, 15 images, 3:2 | 13 images, 1500 × 1000 |

To change the story, edit `about-the-project.template.md`, then rebuild. Numbers come from `engine/eval/results`, so do not type them into the story.

```sh
cd submission
python3 visuals/build_diagrams.py
../engine/.venv/bin/python visuals/build_charts.py
python3 build_story.py
```

## Images in the story

Devpost's Markdown needs public image URLs. `about-the-project.md` uses local paths for now.

1. Upload all 13 PNGs to the Image gallery.
2. For inline images, host them somewhere public, then rebuild with that base URL:

```sh
python3 build_story.py https://raw.githubusercontent.com/YOUR_NAME/ufinder/main/submission/visuals/
```

A public GitHub repo also fills the "Try it out" field. Do not include `engine/models` or `engine/data`. The `.gitignore` already excludes them. The screenshots show COCO photos with faces blurred, some with brand marks in the background, so review them before posting.

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

**Elevator pitch** (200 max, this is 172):

> Find any file on your UGREEN NAS by what is inside it. One search across photos, documents, recordings and video, with evidence for every match. Your files stay on the NAS.

**About the project:** paste `about-the-project.md`.

**Built with** (25 max): `ugos`, `uliya`, `docker`, `python`, `sqlite`, `qdrant`, `qwen`, `fastapi`, `ffmpeg`, `faster-whisper`, `rapidocr`, `mcp`, `markdown`

**Try it out links:** a public repo, if you create one. Not required.

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
