#!/usr/bin/env python3
"""
Convert a SNAP edge list to the adjacency-list format expected by NeighborSig-Match.

Output line format:
    nodeId<TAB>nodeLabel<TAB>neighbor1:neighborLabel:edgeLabel,neighbor2:neighborLabel:edgeLabel,...

By default:
- comment lines starting with # are ignored
- edge label is constant 'E'
- node labels are assigned deterministically as L{node_id % num_labels}
- graph is treated as undirected unless --directed is used
"""

import argparse
import gzip
from collections import defaultdict
from pathlib import Path


def open_maybe_gzip(path: Path):
    if str(path).endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8')
    return open(path, 'r', encoding='utf-8')


def assign_label(node_id: str, num_labels: int) -> str:
    try:
        value = int(node_id)
    except ValueError:
        value = abs(hash(node_id))
    return f"L{value % num_labels}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='SNAP edge list .txt or .txt.gz')
    parser.add_argument('--output', required=True, help='Output adjacency-list file')
    parser.add_argument('--directed', action='store_true', help='Keep graph directed')
    parser.add_argument('--num-labels', type=int, default=8, help='Synthetic node label cardinality')
    parser.add_argument('--edge-label', default='E', help='Edge label to attach to all edges')
    args = parser.parse_args()

    adjacency = defaultdict(set)
    all_nodes = set()

    with open_maybe_gzip(Path(args.input)) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            src, dst = parts[0], parts[1]
            all_nodes.add(src)
            all_nodes.add(dst)
            adjacency[src].add(dst)
            if not args.directed:
                adjacency[dst].add(src)

    labels = {node: assign_label(node, args.num_labels) for node in all_nodes}

    with open(args.output, 'w', encoding='utf-8') as out:
        for node in sorted(all_nodes, key=lambda x: (len(x), x) if not x.isdigit() else (0, int(x))):
            nbrs = sorted(adjacency.get(node, set()), key=lambda x: (len(x), x) if not x.isdigit() else (0, int(x)))
            tokens = [f"{nbr}:{labels[nbr]}:{args.edge_label}" for nbr in nbrs]
            out.write(f"{node}\t{labels[node]}\t{','.join(tokens) if tokens else '-'}\n")

    print(f"Wrote adjacency list to {args.output}")
    print(f"Nodes: {len(all_nodes)}")
    print(f"Directed: {args.directed}")


if __name__ == '__main__':
    main()
