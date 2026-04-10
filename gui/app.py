#!/usr/bin/env python3
import os
import subprocess
import time
from pathlib import Path

from flask import Flask, render_template, request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
STATIC_DIR = APP_ROOT / 'static'
GENERATED_DIR = APP_ROOT / 'generated'
GENERATED_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = Flask(__name__)


def parse_query_form(nodes_text: str, edges_text: str, directed: bool):
    node_lines = [x.strip() for x in nodes_text.splitlines() if x.strip()]
    edge_lines = [x.strip() for x in edges_text.splitlines() if x.strip()]

    lines = [f'directed={str(directed).lower()}']
    for line in node_lines:
        node_id, label = [p.strip() for p in line.split(',')[:2]]
        lines.append(f'v {node_id} {label}')
    for line in edge_lines:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) == 2:
            src, dst = parts
            label = 'E'
        else:
            src, dst, label = parts[:3]
        lines.append(f'e {src} {dst} {label}')
    return '\n'.join(lines) + '\n'


def render_graph(query_path: Path, output_png: Path, highlight_nodes=None):
    directed = False
    G = nx.DiGraph()
    with open(query_path, 'r', encoding='utf-8') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('directed='):
                directed = line.split('=', 1)[1].strip().lower() == 'true'
                G = nx.DiGraph() if directed else nx.Graph()
                continue
            parts = line.split()
            if parts[0] == 'v':
                G.add_node(parts[1], label=parts[2])
            elif parts[0] == 'e':
                edge_label = parts[3] if len(parts) >= 4 else 'E'
                G.add_edge(parts[1], parts[2], label=edge_label)

    plt.figure(figsize=(6, 4))
    pos = nx.spring_layout(G, seed=7)
    node_colors = []
    highlight_nodes = set(highlight_nodes or [])
    for node in G.nodes():
        node_colors.append('orange' if node in highlight_nodes else 'skyblue')
    nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=1200, font_size=9)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=nx.get_edge_attributes(G, 'label'), font_size=8)
    nx.draw_networkx_labels(G, pos, labels={n: f"{n}\n{G.nodes[n].get('label','')}" for n in G.nodes()}, font_size=8)
    plt.tight_layout()
    plt.savefig(output_png, bbox_inches='tight')
    plt.close()


def hdfs_cat(path: str) -> str:
    proc = subprocess.run(f'hdfs dfs -cat {path}', shell=True, text=True, capture_output=True)
    return proc.stdout if proc.returncode == 0 else ''


def candidate_count(path: str) -> int:
    total = 0
    for line in hdfs_cat(path).splitlines():
        parts = line.split('\t')
        if len(parts) < 2 or parts[1].strip() in ('', '-'):
            continue
        total += len(parts[1].split(','))
    return total


def line_count(path: str) -> int:
    data = hdfs_cat(path)
    return len([x for x in data.splitlines() if x.strip()])


def first_match_mapping(path: str):
    data = hdfs_cat(path)
    for line in data.splitlines():
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        mapping = {}
        for token in parts[1].split(','):
            q, d = token.split('=')
            mapping[q] = d
        return mapping
    return None


@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    default_nodes = 'q0,L0\nq1,L1\nq2,L2'
    default_edges = 'q0,q1,E\nq1,q2,E'

    if request.method == 'POST':
        nodes_text = request.form.get('nodes', default_nodes)
        edges_text = request.form.get('edges', default_edges)
        directed = request.form.get('directed') == 'on'
        mode = request.form.get('mode', 'signature')
        k = request.form.get('k', '2')

        query_text = parse_query_form(nodes_text, edges_text, directed)
        query_path = GENERATED_DIR / 'query.txt'
        query_path.write_text(query_text, encoding='utf-8')

        query_png = STATIC_DIR / 'query.png'
        render_graph(query_path, query_png)

        result = {
            'query_png': 'static/query.png',
            'match_png': None,
            'metrics': None,
            'nodes': nodes_text,
            'edges': edges_text,
            'mode': mode,
            'k': k,
        }

        if request.form.get('run_backend') == 'yes':
            adj_dir = os.environ.get('HDFS_ADJ_DIR', '/projects/graphmatch/input/adj')
            base_out = os.environ.get('HDFS_BASE_OUTPUT', '/projects/graphmatch/output/gui')
            jar_path = os.environ.get('HADOOP_JAR', str(PROJECT_ROOT / 'dist' / 'neighborsig-match.jar'))
            start = time.time()
            proc = subprocess.run(
                ['bash', str(PROJECT_ROOT / 'scripts' / 'run_pipeline.sh'), adj_dir, str(query_path), base_out, mode, str(k), jar_path],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )
            elapsed = round(time.time() - start, 3)
            if proc.returncode == 0:
                cand_path = f'{base_out}/candidates_{mode}/part-r-00000'
                match_path = f'{base_out}/matches_{mode}/part-r-00000'
                mapping = first_match_mapping(match_path)
                if mapping:
                    match_query_path = GENERATED_DIR / 'query.txt'
                    match_png = STATIC_DIR / 'match.png'
                    render_graph(match_query_path, match_png, highlight_nodes=set(mapping.keys()))
                    result['match_png'] = 'static/match.png'
                result['metrics'] = {
                    'cpu_time_sec': elapsed,
                    'candidate_count_after': candidate_count(cand_path),
                    'match_count': line_count(match_path),
                    'match_example': mapping,
                }
                result['stdout'] = proc.stdout
            else:
                result['error'] = proc.stderr or proc.stdout

    return render_template('index.html', result=result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
