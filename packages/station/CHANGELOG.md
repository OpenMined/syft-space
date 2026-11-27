# Syft Station changelog

What changed in each Syft Station release. Newest first. A release is one
version of the image `ghcr.io/openmined/syft-station:<version>` and of the
Helm chart, tagged `station-<version>` in git.

The release workflow adds an entry on every release, from the titles of the
pull requests merged since the previous one. Correct an entry with a normal
pull request.

## 0.2.4 (2026-11-27)

### Added

- Optional telemetry collector for spaces ([#293](https://github.com/OpenMined/syft-space/pull/293))
- Trace the station itself; no query strings in traces ([#294](https://github.com/OpenMined/syft-space/pull/294))
