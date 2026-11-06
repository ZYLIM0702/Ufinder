# Ufinder engine

A private vector and graph index for a NAS. It reads your folders, works out what is inside each file and how files connect, and answers search with no LLM. It runs in containers with read-only access to your files and no route to the internet.

This is the optional part of Ufinder. The Skill works without it.

## What runs

| Service | Job | Network | Port |
|---|---|---|---|
| `edge` | Forwards one port to the gateway. Holds no data | LAN and sealed | 8787 |
| `gateway` | Login, keys, per-user filter, content tiers, audit, REST, MCP, Web UI | Sealed | None |
| `indexer` | Scan, extract, resolve the graph | Sealed | None |
| `embedder` | Local model, Qwen3-VL-Embedding-2B | Sealed | None |
| `qdrant` | Vector storage | Sealed | None |
| `egress` | Off by default. One allowed host, for a model endpoint the owner connects | Both | None |

## Run it

Requirements: Docker Compose, about 14 GB of free RAM, and 6 GB of disk for images and weights. The model uses about 9 GB of RAM in `float32`.

1. Put the model weights in `models/`. After that, nothing downloads at runtime.

   ```sh
   hf download Qwen/Qwen3-VL-Embedding-2B --revision 9f2f7e710d6d81056aa5c0a4f04764fec6bb7bda --local-dir models/qwen3-vl-embedding-2b
   hf download Systran/faster-whisper-base --local-dir models/whisper/base
   ```

2. Choose folders and users in `config/ufinder.json`. Each folder lists who may read it. Change the sample passwords.

3. Point the stack at your folders, then start it.

   ```sh
   UFINDER_SOURCE_ROOT=/path/to/folders UFINDER_EXCHANGE_ROOT=/path/to/users docker compose up -d
   ```

4. Open `http://NAS-IP:8787`. Search works immediately and improves as indexing runs.

On a UGREEN NAS, give the folders to a dedicated read-only UGOS user and run the containers as that user. That adds a second lock on top of the read-only mount.

## Connect an agent

Create a key under **Keys and models**, then:

```text
MCP     http://NAS-IP:8787/mcp     Authorization: Bearer YOUR_KEY
REST    POST /v1/search            {"q": "lease renewal"}
Graph   GET  /v1/files/{id}/related
Changes GET  /v1/changes?since=0
Models  POST /v1/embeddings        OpenAI-compatible, uses the local model
```

## Connect a frontier model

The local model is the default. To use another model for chosen folders:

1. Set `"external_embedding": true` on those folders in `config/ufinder.json`.
2. Start the egress door with one allowed host:

   ```sh
   UFINDER_EGRESS_ALLOW=api.example.com UFINDER_EGRESS_PROXY=http://egress:8899 docker compose --profile egress up -d
   ```

3. Connect the endpoint as admin:

   ```sh
   curl -X PUT http://NAS-IP:8787/v1/models/external -H 'Content-Type: application/json' \
     -d '{"base_url":"https://api.example.com/v1","model":"NAME","api_key":"KEY","dim":1024}'
   ```

Text from opted-in folders goes to that endpoint. Everything else stays on the local model. A search query goes out only when a signed-in person sets `use_external: true` on that search. Agent keys cannot do this.

## Add a file type

Write one extractor and register it. See `ufinder/extractors/documents.py`.

```python
register(Plugin("markdown-slides", 1, "text", (".mdx",), my_extractor))
```

## Test it

```sh
python eval/make_corpus.py --out data/sources
docker compose up -d
python eval/system_tests.py
python eval/frontier_test.py
python eval/connection_sample.py
python eval/mcp_client_test.py
```

Measured results are in `docs/RESULTS.md`. The held-out query set is locked by the hash in `eval/results/holdout.sha256`.

## Credits

Evaluation photos come from COCO val2017, with faces blurred, and are used for evaluation only. They are not distributed here. Qwen3-VL-Embedding-2B and Qdrant are Apache-2.0. faster-whisper and RapidOCR are MIT and Apache-2.0.
