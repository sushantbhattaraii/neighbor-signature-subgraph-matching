#!/usr/bin/env python3
"""Create smaller induced subgraphs for 10K / 100K / 1M-node experiments."""

import argparse
from collections import defaultdict


def read_adjacency(path):
    graph = {}
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            node_id, label = parts[0], parts[1]
            neighbors = parts[2] if len(parts) > 2 else '-'
            graph[node_id] = (label, neighbors)
    return graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-nodes', type=int, required=True)
    args = parser.parse_args()

    graph = read_adjacency(args.input)
    selected = set(list(graph.keys())[:args.max_nodes])

    with open(args.output, 'w', encoding='utf-8') as out:
        for node_id in list(graph.keys())[:args.max_nodes]:
            label, neighbors = graph[node_id]
            if neighbors == '-':
                out.write(f"{node_id}\t{label}\t-\n")
                continue
            kept = []
            for token in neighbors.split(','):
                nbr = token.split(':', 1)[0]
                if nbr in selected:
                    kept.append(token)
            out.write(f"{node_id}\t{label}\t{','.join(kept) if kept else '-'}\n")

    print(f"Wrote sampled induced subgraph with up to {args.max_nodes} nodes to {args.output}")


if __name__ == '__main__':
    main()
