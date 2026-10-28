# Independent development experiment

- Work in this directory. During construction, use only the configuration pair under `data/raw/`. Do not inspect other projects, configuration samples, translator implementations, or evaluation reports. General tooling, dependencies, and public official model/command documentation are allowed.
- Preserve the bytes of the two raw files. Their hashes are in `data/manifest.json`. Save derived documents separately.
- The user confirmed on 2026-10-27 that the reference CLI is H3C. Use the official manual under `references/h3c-s9827-s9857-r932x-6w101/` as the primary command reference; read its README first. The S9827/S9857 Release 9323 reference is a selected development reference, not confirmation of the source device model or running software. Record remaining model/NOS/version and paired snapshot uncertainty.
- Build a parameterized translator for complete documents. Runtime must be offline and deterministic, without model calls or reading the development reference CLI. Do not return saved reference output by matching a device name, path, or hash.
- Report unsupported, ambiguous, and erroneous input explicitly. Do not silently remove input content to claim full support.
- Record development checks, source versions, usage, and the frozen implementation identity. Do not seek additional test material; later evaluation is separately supplied by the user.
