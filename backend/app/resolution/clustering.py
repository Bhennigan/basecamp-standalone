"""Transitive closure of MATCH pairs into entity clusters via union-find.

If A matches B and B matches C, then A, B, C resolve to one entity even when A and C
were never directly compared (e.g. blocking never put them in the same block). We take
the connected components of the graph whose edges are the MATCH pairs.

Choice on singletons: a record that participated in no MATCH pair is *not* returned as
a one-element cluster. Only records "touched" by at least one match edge appear in the
output. Callers that want every record represented (singletons as their own golden
record) should handle the un-clustered remainder separately — the resolution service
does exactly this.
"""
from __future__ import annotations

from typing import Iterable


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # Path compression.
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def cluster(pairs: list[tuple[int, int]]) -> list[set[int]]:
    """Return connected components (clusters of size >= 2) over the MATCH pairs.

    Order of returned clusters and of members within is not significant.
    """
    uf = _UnionFind()
    for a, b in pairs:
        uf.union(a, b)

    components: dict[int, set[int]] = {}
    seen: Iterable[int] = list(uf.parent.keys())
    for node in seen:
        root = uf.find(node)
        components.setdefault(root, set()).add(node)

    # Every node here participated in at least one edge, so every component is >= 2.
    return [members for members in components.values() if len(members) >= 1]
