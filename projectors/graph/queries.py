from typing import Any, Dict, List

from services.common.graph_adapter import GraphAdapter


class GraphQueries:
    """High-level graph query helper using GraphAdapter"""

    def __init__(self, adapter: GraphAdapter):
        self.adapter = adapter

    async def find_connected_notes(
        self, world_id: str, branch: str, note_id: str, max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        query = f"""
            MATCH (start:Note {{id: $note_id, world_id: $world_id, branch: $branch}})
            MATCH (start)-[:LINKS_TO*1..{max_depth}]->(connected:Note)
            WHERE connected.world_id = $world_id AND connected.branch = $branch
            RETURN DISTINCT connected.id as id,
                   connected.title as title,
                   connected.created_at as created_at
        """
        return await self.adapter.execute_cypher(
            world_id,
            branch,
            query,
            {"note_id": note_id, "world_id": world_id, "branch": branch},
        )

    async def find_notes_by_tag(
        self, world_id: str, branch: str, tag: str
    ) -> List[Dict[str, Any]]:
        query = f"""
            MATCH (n:Note {{world_id: $world_id, branch: $branch}})
            MATCH (n)-[:TAGGED {{world_id: $world_id, branch: $branch}}]->(
                t:Tag {{tag: $tag, world_id: $world_id, branch: $branch}}
            )
            RETURN n.id as id, n.title as title, n.created_at as created_at
            ORDER BY n.created_at DESC
        """
        return await self.adapter.execute_cypher(
            world_id,
            branch,
            query,
            {"world_id": world_id, "branch": branch, "tag": tag},
        )

    async def get_graph_statistics(self, world_id: str, branch: str) -> Dict[str, Any]:
        stats_queries = {
            "node_count": "MATCH (n) RETURN COUNT(n) as count",
            "edge_count": "MATCH ()-[r]->() RETURN COUNT(r) as count",
            "note_count": "MATCH (n:Note) RETURN COUNT(n) as count",
            "tag_count": "MATCH (t:Tag) RETURN COUNT(t) as count",
            "link_count": "MATCH ()-[r:LINKS_TO]->() RETURN COUNT(r) as count",
            "tagged_count": "MATCH ()-[r:TAGGED]->() RETURN COUNT(r) as count",
        }

        stats: Dict[str, Any] = {}
        for stat_name, query in stats_queries.items():
            result = await self.adapter.execute_cypher(world_id, branch, query)
            stats[stat_name] = result[0]["count"] if result else 0

        return stats
