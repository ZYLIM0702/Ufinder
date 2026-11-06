# Research notes

Checked on 2026-11-06. Each section ends with what it means for the build. Sources are listed at the end. Where a fact comes from a review and not from UGREEN, it says so.

## 1. UGREEN: what exists today

### Hardware (iDX6011 Pro)

The product page was rate-limited, so these figures come from TechRadar and Dong Knows Tech.

| Item | Fact |
|---|---|
| CPU | Intel Core Ultra 7 255H, 16 cores |
| AI compute | 96 TOPS claimed, platform total. NPU share not confirmed |
| RAM | 64GB LPDDR5X, soldered |
| Storage | 6 bays, separate 128GB system SSD for UGOS and Uliya |
| Network | Dual 10GbE, dual Thunderbolt 4 |
| Expansion | OCuLink, PCIe 4.0 x8 |
| Hackathon test unit | iDX6011 Pro 64GB, one day of remote access |

Sibling iDX6011 models use a Core Ultra 5 125H with 32GB or 64GB. Most other UGREEN NAS units have far less RAM, for example 8GB on the DH4300 Plus. A design that only works in 64GB fails the wider product line.

### Software already on the NAS

- **UGREEN Photos** already does local people, pet, scene and OCR recognition, and **semantic search with descriptive phrases**, once the models are downloaded.
- **Custom Learning** lets users label photos to train new object categories. This is the page you linked (article 322).
- **Universal Search** covers photos, videos, documents and apps with keywords or natural phrases.
- **Uliya** is the on-device assistant. It runs a local model by default, and reviews name Qwen3. AI Console adds other models. Cloud models connect through a paid API key.
- **Docker, VMs, OpenClaw, Voice Memos** with on-device transcription are also listed for UGOS.

### Where it falls short (independent reviews, versions differ, so re-check on the NAS)

- TechRadar: document semantic search "worked well for labelled files, but was less effective at finding content within documents."
- TechRadar: photo indexing "requires re-indexing after new uploads to reliably recognise content" and was "a little hit-and-miss."
- TechRadar: chatbot search and file integration felt "slightly limited", "more like a chatbot than a true AI assistant."
- Club386: asked for "all my photos of dogs", Uliya replied that it could not access personal files or photos.
- TechRadar: sorting and renaming at scale needed a cloud model over SSH.

### What the Skill API can reach

Nine CLIs, six expert agents. Verified in `uliya-skill-kit/data/capability-catalog.json`.

| Agent | CLIs | Useful actions |
|---|---|---|
| file-agent | ug-filesystem, ug-filemgr, file-workflow | find, ls, stat, sha256sum, scan-dedupe, tags, plan and run |
| photo-agent | ug-photo | search-picture (`ocr-contains`, object, person, place, time), search-screen, vision-ocr, vision-vlm, create-album |
| document-agent | ug-document | qa (`semantic_lookup`, `locate_content`), extract, reconcile, translate |
| knowledge-agent | ug-knowledge | collect-evidence, audio-transcription, save-text |
| media-agent | ug-video, ug-music | search, subtitles, playback |
| security-monitor-agent | ug-surveillance | events, faces, plates, evidence |

Not in the catalog: search by image or audio, one search across domains, a file change feed, a shared index, Docker control, any network call. Most `permissions` fields read `knowledgeStatus: unknown`, so real permission behaviour must be tested on the NAS.

### Official app packaging (the path to OS-level)

This is on [developer.ugnas.com](https://developer.ugnas.com/en), separate from Skills.

| Topic | Docker APP | Native APP |
|---|---|---|
| Package | UPK, `ugcli pack`, images bundled by `docker save` | UPK, `ugcli pack` |
| Language | Any, inside images | "compiled languages like C/C++, or Go" |
| Forbidden | `privileged`, `cap_add`, host network, host PID or IPC | Not stated |
| Folder access | `path` parameters chosen at install | `allow_add_access_path`, user grants folders |
| Internet | Not stated | Only with `NETWORK.ACCESS_INTERNET` |
| Runs as | Container | Own non-root user, own file view |
| Start | `restart: always` in the sample | Auto-start after install, SIGTERM then SIGKILL after 10s |

Shared across both:

- **Login**: the system gateway injects `Ugreen-User-ID`, `Ugreen-User-Name` and `Ugreen-User-Type` headers. Requires `open_type: inner`. The docs do not explain how to verify the token.
- **Ports**: declared port gets HTTP and HTTPS proxying and **automatic remote access through UGREENlink**. That matters for privacy, see DESIGN section 4.
- **Device setup**: firmware 1.13 or later, plus a `ugdev.sig` file obtained by emailing UGREEN the serial number, MAC and admin name.
- **Listing**: identity verification takes 3 to 7 working days. Review bans long CPU, memory or disk monopolies, secret scanning, and post-listing model downloads without re-review.

### Rules that shape the design

| Rule | Source | Effect |
|---|---|---|
| `SKILL.md` plus `references/*.md` only | Official Rules, kit checker | No Compose file, no installer |
| Parent uses only `delegate` to six agents | Kit `SKILL.md` | Skill cannot run anything |
| "Custom executable scripts, general-purpose programming runtimes, and unauthorized direct access to NAS resources are not supported" | Official Rules | Skill cannot host the engine |
| No "registering resident services, or creating background daemon processes" | SkillHub 5.4 | Skill cannot own an indexer |
| No loopback or private addresses | SkillHub 6.2 | Skill cannot call a local API |
| "direct calls to unsupported third-party APIs... are prohibited" | Hackathon FAQ | Same |
| No sudo, no "requiring the download and execution of unknown code" | SkillHub 2.7, 4.6 | Skill cannot walk users through installs |
| No searching `.env`, `.git`, keys, certificates | SkillHub 7.1 | Excluded by default |
| Biometric identification is high-risk | SkillHub 9.3 | Reuse People albums, no own face model |
| Judges test the Final Skill Package on the assigned NAS | Official Rules | It must work with nothing else installed |
| Proposal must list third-party components, licenses, data flows | Official Rules | Done in PDF appendix |
| List every AI tool used. Skip AI for naming, description, PDF, core idea | FAQ | See submission notes |

### Checker result for the Docker idea

A copy of the Skill with a Compose file, an install script, a shell block, a download, a `/volume1` path, a local HTTP call and an invented `docker-agent` returned `not-uploadable`. See `submission/README.md` for the exact error codes.

**Meaning:** a Skill cannot spin up Docker. The engine must be a separate thing that the owner installs. Our real claim against UGREEN's product is not "the NAS cannot do this". It is "each app has its own AI, nothing joins them, and agents have no stable API".

## 2. Obsidian's architecture: what we learned from it

Internal notes only. The submission does not mention or integrate with Obsidian. We studied how it works and applied the ideas to our own core.

Sources: the public API (`obsidian.d.ts`), official help pages, and one community runtime probe of the app (issue #513 in `obsidian-remote-ssh`). Internal details from that probe are observations of a running app, not documented behaviour.

### How it works

| Part | What it does |
|---|---|
| Files are the truth | Notes are plain files. The cache can always be rebuilt from them |
| Metadata cache | Per-file parsed records (`CachedMetadata`): links, embeds, tags, headings, sections, blocks |
| Startup | Per the probe, cached paths whose mtime and size match are kept and never read |
| Parse, then resolve | `changed` fires per file. `resolve` and `resolved` fire later, once links are worked out |
| Link maps | `resolvedLinks[src][dst] = count`. `unresolvedLinks` keeps links to files that do not exist |
| Link matching | `getFirstLinkpathDest` picks the best match using the source file's location |
| Sub-file links | A link can target a heading or block inside a file |
| Backlinks | Linked mentions, plus **unlinked mentions** found by matching a note's name in plain text |
| Graph view | Global and local, depth slider, filters, orphans, groups. Larger nodes have more links |
| Search operators | `path:`, `file:`, `tag:`, `[property:value]`, boolean logic |
| Storage adapter | `DataAdapter` hides the file system from everything above it |
| Extensions | `registerExtensions` maps a file type to a handler |
| Safe writes | `Vault.process` is an atomic read-modify-write. `FileManager.renameFile` updates links |

### What changed in our design because of it

| Idea | Our version | Why it is better on a NAS |
|---|---|---|
| Rebuildable cache | The index is disposable, files are the truth | A corrupt index never risks data |
| Skip unchanged files at startup | Scan compares size, mtime, inode and reads nothing if they match | Restart cost stays near zero. Tested: 457 files skipped after `kill -9` |
| Two-level cache | `files`: path to content. `blobs`: content to meaning | Rename, copy and duplicate re-embed nothing |
| Parse, then resolve | Extractors are pure per-file functions. Graph work runs separately | Extraction is cacheable and resumable. Links need global knowledge |
| `unresolvedLinks` | Ghost nodes for files that are mentioned but missing | Tells users what is missing. Links up by itself |
| Unlinked mentions | Entity hubs and plain-text file mentions, found through the inverted index | Links appear from OCR and speech too, which no one typed |
| Link matching | Same folder first, then shortest path | Same rule for mentions in documents |
| Sub-file links | Chunks keep a locator: page, timestamp, image text | Results point at page 3 or 01:12 |
| Local graph | Depth-limited view, plus graph retrieval from search hits | The graph is part of search, not only a picture |
| Search operators | `type:`, `path:`, `after:`, `before:` | Deterministic filters with no LLM |
| `DataAdapter` | `StorageAdapter` | Docker today, UGOS feed later, same code above it |
| `registerExtensions` | Extractor plugins | A new file type is one class. Bumping a version re-extracts only that type |
| Change events | `events` feed: create, modify, rename, delete, changed, resolved | The same feed drives the UI, agents and n8n |

### Where we go further

- **Links are derived, not typed.** The graph comes from content, time, hashes and vectors, each with evidence.
- **Multi-user.** Graph walks skip files the user cannot read.
- **Scale.** The community reports stalls around 10,000 notes, so we never mirror files as notes. The graph lives in the engine.

## 3. Elasticsearch and Jina: the algorithms

### What Elasticsearch does

1. **BM25** on an inverted index, on Lucene segments. Strong analyzers, including CJK.
2. **HNSW** for approximate nearest neighbours, a layered graph. Search walks it greedily.
3. **BBQ**: 1 bit per dimension, 32x smaller, with 14 bytes of corrective data. Queries use 4 bits. It retrieves 3x candidates and rescores with the full vectors on disk.
4. **DiskBBQ**: hierarchical k-means clusters kept on disk. Lowest RAM, good to about 95% recall.
5. **ACORN** filtered HNSW: applies filters during graph traversal, so selective filters stay fast. This matters for per-user search.
6. **RRF** merges rankings without comparing scores:

$$\text{score}(d) = \sum_{r \in \text{rankers}} \frac{1}{k + \text{rank}_r(d)}, \quad k = 60$$

### Memory, using Elastic's own formulas

For 1,000,000 vectors at 1024 dimensions:

| Item | Formula | Size |
|---|---|---|
| Raw vectors on disk | n × d × 4 | 4.10 GB |
| BBQ in RAM | n × (⌈d/64⌉ × 8 + 14) | 142 MB |
| HNSW graph in RAM | n × 4 × 16 | 64 MB |

So vector memory is small. Vectors are not the problem.

### Why not Elasticsearch on the default path

Elastic's subscription matrix dated 2026-08-04, read from the rendered PDF:

| Feature | Free Basic |
|---|---|
| Vector search, standard and kNN retrievers, RBAC, API keys | Yes |
| RRF, linear retriever, reranking retriever | **No, Enterprise** |
| DiskBBQ | **No, Enterprise** |
| Field and document level security | **No, Platinum or Enterprise** |
| Encryption at rest support | **No, Platinum or Enterprise** |
| Audit logging | **No, Platinum or Enterprise** |

Three more reasons:

- An always-on JVM is the memory complaint you started with. UGREEN's app review also bans long memory monopolies.
- Native APPs must be compiled, so a JVM engine can never leave Docker.
- Bundling it into an appliance needs a license review of ELv2, AGPLv3 and SSPL. Not done here.

Keep the ideas, drop the service: **BM25 plus dense vectors, quantize, filter during search, fuse with RRF.** RRF is ten lines in our gateway.

| Need | Default | Why |
|---|---|---|
| File table, jobs, graph edges, audit | SQLite (WAL) | One file, transactional, public domain |
| Keyword search | SQLite FTS5 with `bm25()` | Lives with the file table |
| Vectors | Qdrant | Rust binary, Apache-2.0, binary quantization, filters, tenant partitions, built-in RRF |
| Fusion, access control | Our gateway | Must see the user identity anyway |

"NoSQL" is not needed. The file table is relational, and Qdrant stores vectors with their payload. If FTS5 falls short on mixed-language text, the `SearchBackend` interface lets us add a Lucene engine later.

### Jina and Qwen models

Elastic bought Jina AI in October 2025. Open models continue on Hugging Face.

| | jina-embeddings-v5-omni-nano | jina v5-omni-small | Qwen3-VL-Embedding-2B |
|---|---|---|---|
| Size | about 1B parameters | about 1.6B | 2B |
| Dimensions | 768 | 1024 | 2048, truncatable |
| Text, image, video | Yes | Yes | Yes |
| Audio | **Yes** | **Yes** | **No** |
| License | **CC BY-NC 4.0** | **CC BY-NC 4.0** | **Apache-2.0** |
| GGUF | Yes, retrieval variant. Multimodal needs Jina's llama.cpp fork | Same | Community builds |
| Reranker | Separate | Separate | Qwen3-VL-Reranker-2B |

Facts that change the plan:

- **Neither is light.** At 1B to 2B parameters these are not background-friendly by default. Q4 text GGUF for small is 396 MB, and the vision and audio projectors ship only in F16. See the measured numbers in RESULTS.md.
- **Uliya runs on the Qwen family**, per reviews, so a Qwen embedding model is a natural fit for the NAS. The family matches. The weights are separate.
- **Qwen3-VL-Embedding-2B needs Transformers 5.** On 4.57 it loads with random weights and only a warning. The embedder now compares a weight tensor with the checkpoint and refuses to start if they differ.
- **Jina is non-commercial.** It is usable for evaluation. UGREEN shipping it, or any commercial use, needs a license from Jina. Competing for a cash prize is a grey area, so disclose it or get written permission.
- **Video in v5-omni embeds frames only.** The soundtrack must be passed as a separate input.
- **Qwen has no audio.** Audio goes through transcription, then text embedding. `ug-knowledge audio-transcription` or whisper.cpp both work.
- **v5 text indexes are compatible with v5-omni**, per Jina's announcement.

**Default:** Qwen3-VL-Embedding-2B, because the license is clean and the Qwen family already ships on UGOS. Run jina-v5-omni-nano beside it in a bake-off.

**Honest limit on your T-shirt example:** a visual embedding will find "a man in a T-shirt". It may not reliably read a small logo. Do not rely on embeddings alone. Fuse with OCR through BM25, then verify the top results with `vision-vlm`. The test will show how far each signal goes.

## 4. Security background

- **C3RB3R ransomware** has hit Synology NAS devices since early October 2026. Synology confirmed attacks on October 29. Whether a zero-day is involved is unconfirmed. No UGREEN incident found. Use this as context only, and do not imply a UGREEN issue.
- **Lethal trifecta** (Simon Willison): private data, untrusted content and external communication together enable prompt injection theft. The fix is to break the combination, not to add prompt rules.
- **MCP auth** (2025-11-25 revision, from secondary sources): OAuth 2.1 with protected resource metadata, audience-bound tokens, no token passthrough. Check the official spec before implementing.
- **n8n**: MCP Client Tool supports Bearer and Header auth. Check the December 2025 bug where a tool selection dropped the Bearer token.
- **Change tracking**: inotify needs one watch per directory. fanotify filesystem marks scale better but need admin privileges, and Docker APPs forbid `cap_add`.

## Sources

**Hackathon and UGREEN**

- [Official Rules](https://ugreenhackathon.devpost.com/rules), [Overview](https://ugreenhackathon.devpost.com/), [Resources and FAQ](https://ugreenhackathon.devpost.com/resources)
- [Starter Kit](https://ai.ugreen.com/pages/hackathon-starter-kit), [SkillHub Publishing Standards](https://api.ugnas.com/api/system/v1/ua/agreement/page?agreementCode=skillhub-publish-audit-spec&acceptLanguage=en-US)
- [Developer docs](https://developer.ugnas.com/en/doc/backend/quick-start/prepare.html), [Docker APP](https://developer.ugnas.com/en/doc/backend/quick-start/develop-docker-app.html), [Runtime](https://developer.ugnas.com/en/doc/backend/application/runtime-environment.html), [Login](https://developer.ugnas.com/en/doc/backend/system-capabilities/login-auth.html), [project.yaml](https://developer.ugnas.com/en/doc/tools/project-yaml.html), [App review](https://developer.ugnas.com/en/doc/review/app-review/audit-key-points.html)
- [UGOS](https://ai.ugreen.com/pages/operating-system), [UGREEN Photos guide](https://ai.ugreen.com/blogs/knowledge/ugreen-nas-photos), [Custom Learning](https://support.ugnas.com/detail/article/en-US/322)
- Reviews: [TechRadar](https://www.techradar.com/computing/ugreen-nasync-idx6011-pro-nas-review), [Dong Knows Tech](https://dongknows.com/ugreen-nasync-idx6011-pro-review/), [Club386](https://www.club386.com/ugreen-nasync-idx6011-pro-review/)

**Obsidian**

- [API types, obsidian.d.ts](https://github.com/obsidianmd/obsidian-api/blob/master/obsidian.d.ts), [How Obsidian stores data](https://obsidian.md/help/data-storage), [Backlinks](https://obsidian.md/help/plugins/backlinks), [Graph view](https://obsidian.md/help/plugins/graph), [Search](https://obsidian.md/help/plugins/search), [Runtime probe, issue 513](https://github.com/sotashimozono/obsidian-remote-ssh/issues/513), [Forum stall report](https://forum.obsidian.md/t/performance-280-ms-renderer-stall-every-2-seconds-in-large-vault-caused-by-getallpropertyinfos/117693)

**Search and models**

- [Elastic subscriptions](https://www.elastic.co/subscriptions), [BBQ](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/bbq), [kNN sizing](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/approximate-knn-search), [Elastic buys Jina](https://businesswire.com/news/home/20251009619654/en/Elastic-Completes-Acquisition-of-Jina-AI)
- [jina v5-omni-nano](https://huggingface.co/jinaai/jina-embeddings-v5-omni-nano), [v5-omni small GGUF](https://huggingface.co/jinaai/jina-embeddings-v5-omni-small-text-matching-GGUF), [Qwen3-VL-Embedding](https://github.com/QwenLM/Qwen3-VL-Embedding)
- [HippoRAG, PPR for retrieval](https://ar5iv.labs.arxiv.org/html/2405.14831v3), [Qdrant multitenancy](https://qdrant.tech/documentation/manage-data/multitenancy/), [Hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/), [Quantization](https://qdrant.tech/documentation/manage-data/quantization/)

**Security and integration**

- [C3RB3R report](https://www.it-connect.tech/c3rb3r-ransomware-is-hitting-synology-nas-devices-how-to-protect-yours/), [Lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), [n8n MCP Server Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.mcptrigger/), [n8n auth bug](https://github.com/n8n-io/n8n/issues/23421), [MCP authorization mirror](https://modelcontextprotocol.info/specification/2025-11-25/basic/authorization/), [fanotify_mark(2)](https://manpages.ubuntu.com/manpages/stonking/man2/fanotify_mark.2.html)
