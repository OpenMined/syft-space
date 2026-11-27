# Syft Space image changelog

What changed in each published Docker image, `ghcr.io/openmined/syft-space`.
Newest first. An image is named by its tag, the short id of the commit it was
built from: `ghcr.io/openmined/syft-space:<tag>`.

The publish workflow adds an entry after every image built from `main`, from
the titles of the pull requests merged since the previous image. Correct an
entry with a normal pull request.

## Docker image b747b19 (2026-11-27)

### Added

- Opentelemetry tracing, off by default ([#291](https://github.com/OpenMined/syft-space/pull/291))
- Trace the station itself; no query strings in traces ([#294](https://github.com/OpenMined/syft-space/pull/294))
- Verify satellite tokens locally, take SyftHub off the query path ([#286](https://github.com/OpenMined/syft-space/pull/286))

### Fixed

- Stop ingest on dataset delete, convert PDFs in batches ([#292](https://github.com/OpenMined/syft-space/pull/292))
