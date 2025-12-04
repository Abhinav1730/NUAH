# Snapshot Schema & Export Format

This document captures the canonical structure for user snapshots exchanged
between `fetch-data-agent` and `trade-agent`. Every snapshot is written twice:

- `data/snapshots/user_<ID>.json` – human readable envelope.
- `data/snapshots/user_<ID>.toon` – compact Protobuf binary (our “TOON” format).

Both files share the same metadata and schema version so we can keep the binary
and JSON views in sync.

## Envelope

```json
{
  "schemaVersion": "1.0.0",
  "generatedAt": "2025-12-04T13:20:31.000Z",
  "sourceAgent": "fetch-data-agent",
  "snapshot": {
    "userId": 42,
    "profile": { "...": "..." },
    "balances": [],
    "transactions": [],
    "portfolio": {},
    "bots": [],
    "marketData": [],
    "fetchedAt": "2025-12-04T13:20:31.000Z"
  }
}
```

- `schemaVersion` is controlled via `SNAPSHOT_SCHEMA_VERSION` (defaults to
  `1.0.0`).
- `generatedAt` is the timestamp when the exporter produced the files.
- `sourceAgent` identifies which agent wrote the snapshot (defaults to
  `fetch-data-agent`).
- `snapshot` matches the structure returned by the n-dollar API with the
  following canonical sections:
  - `profile`
  - `balances[]`
  - `transactions[]`
  - `portfolio` (with `tokens[]`, `totalValueNDollar`, `totalValueSOL`, `count`)
  - `bots[]`
  - `marketData[]`

## Protobuf (“TOON”) schema

The `.toon` file uses a compact Protocol Buffer definition that mirrors the JSON
payload. The root message is `nuah.UserSnapshot`:

```
message UserSnapshot {
  uint32 user_id = 1;
  string schema_version = 2;
  string generated_at = 3;
  string source_agent = 4;
  Profile profile = 5;
  repeated Balance balances = 6;
  repeated Transaction transactions = 7;
  Portfolio portfolio = 8;
  repeated Bot bots = 9;
  repeated MarketData market_data = 10;
}
```

Supporting messages (`Profile`, `Balance`, `Transaction`, `Portfolio`,
`PortfolioToken`, `Bot`, `MarketData`) carry the same field names as the JSON
envelope. Optional values are transmitted as empty strings/defaults so the
decoder can rely on a stable schema even when upstream data omits fields.

To decode in Python:

```python
import protobuf
from snapshot_pb2 import UserSnapshot

with open("data/snapshots/user_42.toon", "rb") as fp:
    payload = UserSnapshot.FromString(fp.read())
```

## Versioning rules

1. Bump `SNAPSHOT_SCHEMA_VERSION` whenever a breaking change is introduced
   (adding/removing fields or changing semantics).
2. Keep prior `.toon` files around for backtests—trade-agent only accepts files
   whose `schemaVersion` matches the configured value.
3. All snapshots include `generatedAt`, so consumers can reject stale files
   using their existing freshness windows.

By codifying the schema and exporting both JSON and TOON, we align with the
original system design (Phase A) and can confidently evolve the data layer.

