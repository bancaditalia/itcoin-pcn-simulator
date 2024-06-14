import sys


def approx_max_cut(g, k):
    def number_of_edges_towards(nodes, node):
        return sum(
            [
                1 if g.has_edge(_node, node) or g.has_edge(node, _node) else 0
                for _node in nodes
            ],
        )

    node_buckets = [set() for _ in range(k)]

    nodes = set(g.nodes())
    while len(nodes) > 0:
        best_node, best_bucket, best_bucket_edge_count = None, None, sys.maxsize
        for n in nodes:
            best_bucket_for_n, best_bucket_edge_count_for_n = min(
                [
                    (nodeBucket, number_of_edges_towards(nodeBucket, n))
                    for nodeBucket in node_buckets
                ],
                key=lambda x: x[1],
            )
            if best_bucket_edge_count_for_n < best_bucket_edge_count:
                best_node, best_bucket, best_bucket_edge_count = (
                    n,
                    best_bucket_for_n,
                    best_bucket_edge_count_for_n,
                )
        nodes.remove(best_node)
        best_bucket.add(best_node)

    return node_buckets
