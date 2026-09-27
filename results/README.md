# results/

One folder per config name (`results/<name>/`), written by `tsfm-rc run`. Each Parquet
file carries a provenance record (config hash, data hash, package versions, git commit)
in its metadata; `provenance.json` holds the same record in readable form.

Only the fixture-based runs (`smoke`, `default_fixtures`) are committed, so that the
numbers in `reports/` can be traced to stored artifacts in the repository.
