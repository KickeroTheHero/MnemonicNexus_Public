# Persona Layer Explainer

The persona layer is responsible for rendering stored Briefs and Artifacts into natural language responses for users.

## Key Principles

1. **Never calls tools directly** - The persona layer only renders pre-computed results
2. **Renders stored artifacts** - Works with Brief and Decision Record artifacts
3. **Natural language output** - Unlike non-persona layer, produces conversational responses
4. **Citation formatting** - Properly formats citations from web search results

## Implementation Note

The persona layer will be implemented in a future phase. For S0, we focus on the non-persona structured output pipeline.

## Separation of Concerns

```
Non-Persona (Structured):
Query → Tool Intent → Tool Execution → Brief → Decision Record

Persona (Natural Language):
Brief + Artifacts → Natural Language Response
```

This separation ensures:
- Deterministic tool execution
- Reproducible decision records
- Clear audit trails
- Consistent structured outputs
