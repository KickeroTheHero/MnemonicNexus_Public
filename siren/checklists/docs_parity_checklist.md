# V2 Documentation Parity Checklist

## Contract Validation
- [ ] OpenAPI vs API examples in `docs/api.md` are in sync (`make docs:check`)
- [ ] Event envelope examples validate against `siren/specs/event.schema.json`
- [ ] All API examples include required `world_id` and `by.agent` fields

## Schema Validation  
- [ ] V2 lens schemas documented in architecture (`lens_rel.*`, `lens_sem.*`, `lens_graph.*`)
- [ ] All documented tables include `world_id UUID NOT NULL` and `branch TEXT NOT NULL`
- [ ] Migration parity check passes for documented V2 schemas

## Development Discipline
- [ ] README reflects V2 development status and roadmap
- [ ] Runbook includes `make docs:check` in standard procedures
- [ ] CHANGELOG.md updated with V2 phase entries
- [ ] All GraphAdapter references include both AGE and Neo4j options

## V2 Architecture Compliance
- [ ] No V1 schema patterns (`rl_*`, `sl_*`) in any documentation
- [ ] All event examples include V2 envelope structure
- [ ] GraphAdapter abstraction properly documented (no direct Neo4j coupling)
- [ ] Tenancy patterns consistent across all examples