# HERD: a 136-package service platform on ARM, Alpine and Windows on ARM

[HERD](https://github.com/vendrabuck/HERD) (Hardware Environment Replication and Deployment) is a lab reservation and topology platform: thirteen FastAPI services in one `uv` workspace, each built into its own image, plus a React frontend. This case study checks its locked dependency set at revision [`9a4b4f6852f44eeffe258d7a5b836e88d0e88353`](https://github.com/vendrabuck/HERD/tree/9a4b4f6852f44eeffe258d7a5b836e88d0e88353) (merged 18 November 2026). The scan used **wheelgap 0.13.0** and the package files available on **19 November 2026** (UTC−03).

The result: 136 registry packages checked, **4 with gaps**, none missing. Three of the four are in the `dev` group, so they affect a developer's machine and CI, not the running images. The fourth is a runtime dependency, and it is the interesting one.

## Targets and selection

HERD's [CI](https://github.com/vendrabuck/HERD/blob/9a4b4f6852f44eeffe258d7a5b836e88d0e88353/.github/workflows/ci.yml#L28) pins Python **3.12**, and every service's image is `python:3.12.16-slim` ([`services/auth/Dockerfile`](https://github.com/vendrabuck/HERD/blob/9a4b4f6852f44eeffe258d7a5b836e88d0e88353/services/auth/Dockerfile)). The scan therefore uses 3.12, matching both.

The three targets are the platforms a self-hosted lab deployment actually meets, not the CI runners:

- `linux-aarch64` — a lab server or NAS on ARM, which is where a reservation platform tends to end up.
- `musl-x86_64` — the Alpine images HERD already uses for its own datastore containers (`postgres:16.15-alpine`, `nats:2.10.29-alpine` in [`docker-compose.yml`](https://github.com/vendrabuck/HERD/blob/9a4b4f6852f44eeffe258d7a5b836e88d0e88353/docker-compose.yml)).
- `win-arm64` — the ARM laptops the engineers who use the platform carry.

Linux uses wheelgap's default glibc floor **2.36**; the service images are Debian slim, so that floor is conservative for them.

## Reproduce the scan

In an empty folder, take the pinned lockfile and check it:

```bash
curl -fL https://raw.githubusercontent.com/vendrabuck/HERD/9a4b4f6852f44eeffe258d7a5b836e88d0e88353/uv.lock -o uv.lock
uvx --from wheelgap==0.13.0 python -m wheelgap uv.lock \
  -p 3.12 -t linux-aarch64,musl-x86_64,win-arm64 \
  --explain --suggest --no-cache
```

Output:

```text
wheelgap 0.13.0 · uv.lock · 136 packages · Python 3.12

skipped 13 non-index packages: herd-acl, herd-ai-orchestrator, herd-auth, … (the workspace members)
⚠ 4 packages have gaps:
  cryptography 50.0.2        win-arm64      source
  gevent 25.9.1              win-arm64      source
  playwright 1.65.0          musl-x86_64    source
  zope-interface 8.3         musl-x86_64, win-arm64  source
```

The command exits **1**. The 13 skipped packages are HERD's own workspace members, installed editable; they are not on any index, and wheelgap says so rather than guessing.

## The runtime gap: `cryptography` on Windows on ARM

`cryptography` is the one gap that reaches a running service. It arrives through `herd-secrets` ([`via`: `herd-secrets`, `cryptography`]), and it has a wheel for `linux-aarch64` and `musl-x86_64` but not for `win-arm64` — every candidate is rejected because it is an x64 or a non-Windows build:

```text
cryptography-50.0.2-cp314-cp314t-win_amd64.whl      win_amd64 doesn't match win-arm64
cryptography-50.0.2-cp311-abi3-win_amd64.whl        win_amd64 doesn't match win-arm64
cryptography-50.0.2-cp314-cp314t-macosx_11_0_arm64.whl  macosx_11_0_arm64 doesn't match win-arm64
… and 44 more
```

That is the usual shape for a Rust-backed package with a mature Windows story: the project publishes `win_amd64` and ARM64 macOS, and Windows on ARM is left to build from source. wheelgap's `--suggest` finds no newer release that closes it, so the options are the ones the flag exists to present:

- build it in CI for `win-arm64` and install the result, which is what a locked image build does when no wheel exists;
- run the Windows node under x64 emulation, where the published wheel applies;
- or accept the source build on that one target.

The other three gaps are all in the `dev` group, so they never reach an image:

- `gevent` and `zope-interface` come through `locust`, the load-test tool. `--suggest` names **gevent 26.5.0** and **zope-interface 8.4** as releases with a `win-arm64` wheel, so a lock refresh is the whole fix.
- `playwright` has no musllinux wheel at all — it ships `manylinux` (glibc) and `win`/`macosx` builds. That is a property of the package, not of HERD: an Alpine-based developer image that installs Playwright has to build it, and the service images avoid the question by being Debian.

## Why this is a good lockfile

The fourteen packages wheelgap cannot check are the workspace itself, and the remaining 136 install from a wheel on `linux-aarch64` — the target a lab server on ARM needs — with no source builds at all. HERD's images are built lock-faithful: `uv export --frozen` turns `uv.lock` into a plain `requirements.txt` per service, so the scan above is the same set the images install.

The four gaps are also honestly placed. Nothing is missing, so no target fails outright; the one runtime gap is a package with no ARM64 Windows wheel, and the rest are developer tooling. For a project that runs in containers and describes its own platform support in its docs, that is the profile the tool is meant to confirm rather than to alarm about.
