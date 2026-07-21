# Source provenance

Version `0.1.0` was extracted on 2026-07-21 from the private accounting monorepo branch
`feat/digital-secretariat-v2` at source commit `cb3cecb`.

The extraction copied the control plane, reference mail rail, focused tests, additive migrations,
database policies, and systemd deployment assets. It did not copy accounting domains, customer
records, mail caches, secrets, local environment files, git history, operational logs, or unrelated
services.

Product-specific changes in this repository remove organization identities and unsafe fallbacks,
make configuration explicit, separate migrations from runtime deploy, and add standalone packaging
and documentation. Future synchronization must use reviewed patches and this repository's public
adapter contracts; do not overwrite it with a raw directory copy from the source monorepo.
