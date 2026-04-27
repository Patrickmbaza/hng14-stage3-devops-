# Architecture Diagram

The placeholder `docs/architecture.png` is invalid and should be replaced with a real exported PNG before final submission.

Use the Mermaid diagram below as the source of truth for the architecture. You can paste it into:

- https://mermaid.live
- draw.io Mermaid import
- Markdown renderers that support Mermaid

Then export the rendered diagram as `docs/architecture.png`.

```mermaid
flowchart TD
    A[Internet Clients]
    B[Nginx Reverse Proxy]
    C[Nextcloud Container]
    D[HNG-nginx-logs Docker Volume]
    E[Python Detector Daemon]
    F[iptables Host Rules]
    G[Slack Webhook]
    H[Live Metrics Dashboard :8081]
    I[Audit Log]
    J[iptables Snapshot Log]

    A -->|HTTP requests| B
    B -->|proxied traffic| C
    B -->|JSON access logs| D
    D -->|tail and parse logs| E

    E -->|DROP abusive IPs| F
    E -->|ban / unban / global alerts| G
    E -->|serve UI and metrics API| H
    E -->|structured events| I
    E -->|BAN/UNBAN snapshots| J

    subgraph Detector Logic
        K[60s deque windows]
        L[30m rolling baseline]
        M[Hour-slot preference]
        N[Z-score and rate multiplier detection]
        O[Auto-unban backoff]
    end

    E --- K
    E --- L
    E --- M
    E --- N
    E --- O
```

## Export Instructions

1. Open `docs/architecture.md` or copy the Mermaid block into Mermaid Live.
2. Render the diagram.
3. Export as PNG.
4. Save the exported file as `docs/architecture.png`.

## Required Final State

Before submission:

- `docs/architecture.md` can remain in the repo
- `docs/architecture.png` must be replaced with a real, valid PNG export
