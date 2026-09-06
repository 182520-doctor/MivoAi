# Local Codex App Server installation

- Source: `https://github.com/openai/codex/releases/tag/rust-v0.153.4`
- Asset: `codex-aarch64-apple-darwin.tar.gz`
- Expected SHA-256: `8cf911ea676523bfb2121ec561848d2aba564890ad536db4d8a3353f2b9850b1`
- Installed binary: `bin/codex-aarch64-apple-darwin`
- Installed binary SHA-256: `b973d440acac501fd2594a43e7ca9ce41e0a65b9dfb28d0d7a7837c99e1261e3`
- Protocol schemas: `schema/json` and `schema/ts`

The backend launches this binary with `app-server --stdio` and communicates over newline-delimited JSON-RPC.

The release checksum applies to the downloaded `.tar.gz` archive. The extracted executable has its own checksum, recorded separately above.
