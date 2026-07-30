# Incident Post-Mortems

## INC-2024-001: DNIF Worker OOM Kill
Date: Jan 15 2024 | Severity: P1 | Duration: 2h 15m

### What Happened
DNIF worker ran out of memory processing a large log burst from a misconfigured firewall.
OOM killer terminated the process at 02:13 IST.

### Root Cause
Firewall misconfiguration sent 10x normal log volume. Worker buffer had no backpressure mechanism.

### Resolution
Restarted worker, added rate limiting on ingestion pipeline, reduced buffer size from 10k to 2k events.

### Prevention
Added memory alert at 80% threshold. Implemented backpressure on ingestion pipeline.

## INC-2024-002: pgvector Index Corruption
Date: Mar 3 2024 | Severity: P2 | Duration: 45m

### What Happened
Abrupt power loss corrupted pgvector HNSW index. All similarity searches returning empty results.

### Root Cause
HNSW index was mid-rebuild during power loss. Partial write left index in invalid state.

### Resolution
Dropped and rebuilt index: DROP INDEX idx_vectors; then re-ran VACUUM ANALYZE.

### Prevention
Added UPS to database server. Enabled WAL archiving for point-in-time recovery.
