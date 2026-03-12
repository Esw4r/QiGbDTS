"""
Network Graph — builds the topology using NetworkX.
"""

import networkx as nx


def build_topology() -> nx.DiGraph:
    """Return a directed graph representing the edge-cloud topology."""
    G = nx.DiGraph()

    nodes = [
        ("edge1", {"type": "edge", "label": "Edge 1"}),
        ("edge2", {"type": "edge", "label": "Edge 2"}),
        ("edge3", {"type": "edge", "label": "Edge 3"}),
        ("scheduler", {"type": "scheduler", "label": "Scheduler"}),
        ("cloud", {"type": "cloud", "label": "Cloud"}),
    ]
    for nid, attrs in nodes:
        G.add_node(nid, **attrs)

    edges = [
        ("edge1", "scheduler"),
        ("edge2", "scheduler"),
        ("edge3", "scheduler"),
        ("scheduler", "edge1"),
        ("scheduler", "edge2"),
        ("scheduler", "edge3"),
        ("scheduler", "cloud"),
        ("cloud", "scheduler"),
    ]
    G.add_edges_from(edges)
    return G
