## Description
<!-- Brief description of the changes -->

## Type of Change
<!-- Mark with [x] -->
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring (no functional changes)

## Contracts Touched
<!-- Mark with [x] all that apply -->
- [ ] OpenAPI specification (`schemas/openapi.json`)
- [ ] JSON schemas (`schemas/json/`)
- [ ] Database schema (migrations)
- [ ] API endpoints (new/modified)
- [ ] Event envelope structure
- [ ] Configuration format

### Contract Changes Details
<!-- If any contracts were touched, describe the changes -->

## Tests Added
<!-- Mark with [x] all that apply -->
- [ ] Unit tests
- [ ] Integration tests  
- [ ] Golden baseline tests
- [ ] Performance tests
- [ ] Security/RLS tests
- [ ] Manual testing performed

### Test Coverage
<!-- Describe what was tested and how -->

## Determinism Risk Assessment
<!-- Mark with [x] and explain -->
- [ ] **NONE** - No impact on determinism
- [ ] **LOW** - Changes isolated to non-deterministic components
- [ ] **MEDIUM** - Changes to event processing but determinism preserved
- [ ] **HIGH** - Changes affect event ordering, replay, or hash generation

### Determinism Impact Details
<!-- If risk is MEDIUM or HIGH, explain mitigation -->

## Rollback Plan
<!-- Describe how to rollback if issues occur -->
- [ ] Simple revert (no data migration required)
- [ ] Requires data migration rollback
- [ ] Requires service restart
- [ ] Requires coordinated rollback

### Rollback Steps
1. 
2. 
3. 

## Security Considerations
<!-- Mark with [x] if applicable -->
- [ ] Changes affect authentication/authorization
- [ ] Changes affect RLS policies
- [ ] Changes affect API key handling
- [ ] Changes affect tenant isolation
- [ ] Security review required

## Performance Impact
<!-- Mark with [x] -->
- [ ] No performance impact expected
- [ ] Minor performance improvement
- [ ] Minor performance degradation (acceptable)
- [ ] Significant performance change (requires review)

## Deployment Notes
<!-- Any special deployment considerations -->

## Checklist
<!-- Mark with [x] before submitting -->
- [ ] Code follows project style guidelines
- [ ] Self-review of code completed
- [ ] Tests pass locally (`make test`)
- [ ] Schemas validate (`make schemas-validate`)
- [ ] Baseline generation succeeds (`make baseline`)
- [ ] Documentation updated (if applicable)
- [ ] Breaking changes documented in commit message
- [ ] Rollback plan documented above

## Related Issues
<!-- Link to related issues using #issue_number -->
Closes #
Related to #

---

### For Reviewers

**Review Checklist:**
- [ ] Code quality and style
- [ ] Test coverage adequate
- [ ] Determinism impact assessed
- [ ] Security implications reviewed
- [ ] Performance impact acceptable
- [ ] Documentation updated
- [ ] Rollback plan viable