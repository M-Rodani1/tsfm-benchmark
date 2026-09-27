# data/raw — immutable raw download cache

Filled by `make fetch-data` (or `make reproduce`). Each download is written once as
`<provider>/<TICKER>__<start>__<end>__<sha256[:12]>.csv` and recorded in `manifest.json`
(source, download time, date range, row count, SHA-256). Files are never overwritten;
a new download with different content gets a new file and a new manifest entry.

This folder is git-ignored (except this README) because Yahoo's terms do not allow
redistribution of the data. Anyone can rebuild it with the command above.
