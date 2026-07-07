# Security Policy

## Supported Versions

CodeAtlas is a small v0.x portfolio project. Security fixes are handled on the current `main` branch and the latest published release line when practical.

## Reporting a Security Issue

Please do not publish active vulnerability details in a public GitHub issue before disclosure has been coordinated.

This repository does not currently advertise a dedicated security email address, and GitHub private vulnerability reporting was checked and found disabled. If private vulnerability reporting is enabled later, use that GitHub feature. Until then, avoid posting exploit details publicly; open a minimal issue asking the maintainer to enable a private reporting path, or use an existing non-public contact channel if one is available to you.

## Current Security Boundaries

- CodeAtlas analyzes public GitHub repositories only.
- Target repository code is not executed.
- Target repository dependencies are not installed.
- Question answering uses the server-owned analysis graph, not client-supplied graph data.
- Optional AI explanation is supplementary to deterministic graph retrieval.
- AI file and symbol references are validated on the server before an explanation is accepted.
- CodeAtlas remains usable without `OPENAI_API_KEY`.

## Useful Security Reports

Security-relevant reports include:

- repository content escaping static-analysis boundaries
- secret or token exposure
- server-side request abuse
- cache analysis isolation failures
- AI validation boundary bypasses

The following limitations are not automatically vulnerabilities:

- incomplete parsing
- unsupported import aliases
- missing call graph support
- retrieval ranking quality
