_Archived from alpha/s0-migration on 2025-01-20; retained for historical context._

# MnemonicNexus V2 Gateway (Contract)

**Version**: 0.2.0
**Generated**: 2025-08-23 20:49:52

Phase A4-A5 Ready - Core event operations with CDC Publisher and multi-lens projector support

## Base Information

- **OpenAPI Version**: 3.0.3
- **Title**: MnemonicNexus V2 Gateway (Contract)
- **Version**: 0.2.0

## Endpoints

### `/v1/events`

- **GET**: List events
- **POST**: Append event

### `/v1/events/{id}`

- **GET**: Get event by id

### `/v1/search/hybrid`

- **POST**: Hybrid search (vector + relational + optional graph expansion)

### `/v1/graph/query`

- **POST**: Bounded graph traversal query

### `/v1/graph/related`

- **GET**: Find related nodes

### `/v1/branches`

- **GET**: List branches
- **POST**: Create branch

### `/v1/branches/{name}`

- **GET**: Get branch by name

### `/v1/branches/{name}/merge`

- **POST**: Merge branch (intent)

### `/v1/branches/{name}/rollback`

- **POST**: Rollback branch (intent)

### `/v1/admin/health`

- **GET**: Admin health (latest global seq + projector watermarks)

### `/v1/admin/projectors`

- **GET**: List projector watermarks and snapshots

### `/v1/admin/projectors/{lens}/snapshot`

- **POST**: Create snapshot markers for all active branches for a lens

### `/v1/admin/projectors/{lens}/restore`

- **POST**: Restore projector lens from snapshot

### `/v1/admin/projectors/{lens}/restore/{job_id}`

- **GET**: Get restore job status

### `/v1/admin/projectors/{lens}/rebuild`

- **POST**: Rebuild projector lens from events

### `/v1/admin/projectors/{lens}/rebuild/{job_id}`

- **GET**: Get rebuild job status

### `/v1/vcs/status`

- **GET**: Get VCS status for all branches

### `/v1/vcs/diff`

- **GET**: Compare branches or branch to specific point

## Schemas

- `Branch`
- `BranchListResponse`
- `CreateBranchRequest`
- `MergeRequest`
- `MergeAccepted`
- `RollbackRequest`
- `RollbackAccepted`
- `EventEnvelope`
- `EventAccepted`
- `Event`
- `EventListResponse`
- `ErrorResponse`
- `HybridSearchRequest`
- `HybridSearchResponse`
- `GraphQueryRequest`
- `GraphQueryResponse`
- `GraphRelatedResponse`


## Contract Schemas

Additional JSON schemas are maintained in `schemas/json/`:
- `tool_intent.v1.json` - Model tool execution plans
- `brief.v1.json` - Structured decision briefs
- `decision_record.v1.json` - Canonical decision records

---

*This documentation is automatically generated from `schemas/openapi.yaml`*
*Run `python scripts/gen-api-docs.py` to regenerate*
