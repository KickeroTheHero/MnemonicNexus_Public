---
name: Bug Report / Feature Request
about: Report a bug or request a new feature for MNX
title: '[BUG/FEATURE] Brief description'
labels: ''
assignees: ''
---

## Issue Type
<!-- Mark with [x] -->
- [ ] Bug Report
- [ ] Feature Request  
- [ ] Performance Issue
- [ ] Security Concern
- [ ] Documentation Issue

## Description
<!-- Provide a clear and concise description -->

## Environment
- **MNX Version**: <!-- e.g., alpha-s0-abc1234 -->
- **Deployment**: <!-- docker-compose, production, development -->
- **OS**: <!-- Linux, Windows, macOS -->
- **Database**: <!-- PostgreSQL version -->

## Steps to Reproduce (for bugs)
1. 
2. 
3. 

## Expected Behavior
<!-- What should happen -->

## Actual Behavior  
<!-- What actually happens -->

## Logs/Error Messages
```
<!-- Paste relevant logs or error messages -->
```

## Determinism & Idempotency Checklist
<!-- Mark with [x] if applicable -->
- [ ] Issue affects event replay determinism
- [ ] Issue affects idempotency guarantees
- [ ] Issue affects multi-tenant isolation
- [ ] Issue affects baseline hash stability
- [ ] Issue affects cross-branch consistency

## Additional Context
<!-- Any other context, screenshots, related issues -->

---

### For Maintainers

**Triage Checklist:**
- [ ] Issue reproduced
- [ ] Appropriate labels assigned
- [ ] Impact on determinism assessed
- [ ] Security implications reviewed
- [ ] Breaking change impact evaluated
