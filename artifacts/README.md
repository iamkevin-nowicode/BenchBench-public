# Published run artifacts

`artifacts/` is the tracked, immutable, append-only home for published run
archives and their manifests. Disposable live output belongs under `runs/`,
which is ignored by Git and must not receive a nested ignore exception.

Before any paid v0.2 transcript is produced, the retention contract is fixed:

1. write resumable transcripts incrementally under the named `runs/` output
   root;
2. archive the completed run with `scripts/build_archive.py`;
3. keep the resulting deterministic tarball and manifest here; and
4. generate the leaderboard only from the retained archive or the explicitly
   named live-run root.

The archive builder refuses to overwrite an existing artifact, scans transcript
bytes and configured key values for credentials before writing anything, and
records a per-transcript SHA-256, model, seed, horizon, engine hash, and prompt
hash. Tar member order, metadata, gzip timestamp, and compression level are
fixed so the tarball SHA-256 is reproducible.

The v0.1 pilot archive is the first published set:

```bash
python3 scripts/build_archive.py \
  --source-dir runs/archive/v0.1-pilot \
  --archive artifacts/v0.1-pilot-transcripts.tar.gz \
  --manifest artifacts/v0.1-pilot-manifest.json \
  --expected-file-count 50 \
  --label "v0.1 pilot" \
  --archive-prefix v0.1-pilot-transcripts \
  --archive-path-label artifacts/v0.1-pilot-transcripts.tar.gz
```

The equivalent v0.2 public-run command is recorded in `release_manifest.json`
before the first smoke or paid transcript is made.
