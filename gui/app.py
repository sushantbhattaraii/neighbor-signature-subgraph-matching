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
    highlight_nodes = set(highlight_nodes or [])
    node_colors = ['orange' if n in highlight_nodes else 'skyblue' for n in G.nodes()]
    nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=1200, font_size=9)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=nx.get_edge_attributes(G, 'label'), font_size=8)
    nx.draw_networkx_labels(
        G,
        pos,
        labels={n: f"{n}\n{G.nodes[n].get('label', '')}" for n in G.nodes()},
        font_size=8
    )
    plt.tight_layout()
    plt.savefig(output_png, bbox_inches='tight')
    plt.close()


def run_cmd(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def hdfs_cat(path: str) -> str:
    proc = run_cmd(['hdfs', 'dfs', '-cat', path])
    return proc.stdout if proc.returncode == 0 else ''


def hdfs_put_file(local_path: Path, hdfs_path: str):
    parent = str(Path(hdfs_path).parent)
    proc1 = run_cmd(['hdfs', 'dfs', '-mkdir', '-p', parent])
    if proc1.returncode != 0:
        raise RuntimeError(proc1.stderr or proc1.stdout)
    proc2 = run_cmd(['hdfs', 'dfs', '-put', '-f', str(local_path), hdfs_path])
    if proc2.returncode != 0:
        raise RuntimeError(proc2.stderr or proc2.stdout)


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


def pruning_ratio(baseline_candidates: int, method_candidates: int) -> float:
    if baseline_candidates <= 0:
        return 0.0
    return round(((baseline_candidates - method_candidates) / baseline_candidates) * 100.0, 2)


def candidate_reduction(baseline_candidates: int, method_candidates: int) -> int:
    return baseline_candidates - method_candidates


def run_pipeline_once(adj_dir: str, hdfs_query_path: str, base_out: str, mode: str, k: int, jar_path: str):
    start = time.time()
    proc = subprocess.run(
        [
            'bash',
            str(PROJECT_ROOT / 'scripts' / 'run_pipeline.sh'),
            adj_dir,
            hdfs_query_path,
            base_out,
            mode,
            str(k),
            jar_path,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    elapsed = round(time.time() - start, 3)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)

    cand_path = f'{base_out}/candidates_{mode}/part-r-00000'
    match_path = f'{base_out}/matches_{mode}/part-r-00000'
    mapping = first_match_mapping(match_path)

    return {
        'mode': mode,
        'k': k,
        'cpu_time_sec': elapsed,
        'candidate_count': candidate_count(cand_path),
        'match_count': line_count(match_path),
        'match_example': mapping,
        'stdout': proc.stdout,
        'cand_path': cand_path,
        'match_path': match_path,
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    default_nodes = 'q0,L0\nq1,L1\nq2,L2'
    default_edges = 'q0,q1,E\nq1,q2,E'
    default_adj_dir = os.environ.get('HDFS_ADJ_DIR', '/projects/graphmatch/input/adj')
    default_base_out = os.environ.get('HDFS_BASE_OUTPUT', '/projects/graphmatch/output/gui')
    default_hdfs_query_path = os.environ.get('HDFS_GUI_QUERY_PATH', '/projects/graphmatch/input/gui/query.txt')
    default_jar_path = os.environ.get('HADOOP_JAR', str(PROJECT_ROOT / 'dist' / 'neighborsig-match.jar'))

    result = {
        'nodes': default_nodes,
        'edges': default_edges,
        'directed': False,
        'mode': 'signature',
        'k': '2',
        'adj_dir': default_adj_dir,
        'base_out': default_base_out,
        'hdfs_query_path': default_hdfs_query_path,
        'query_png': None,
        'match_png': None,
        'single_metrics': None,
        'comparison_rows': None,
        'error': None,
        'stdout': None,
    }

    if request.method == 'POST':
        result['nodes'] = request.form.get('nodes', default_nodes)
        result['edges'] = request.form.get('edges', default_edges)
        result['directed'] = request.form.get('directed') == 'on'
        result['mode'] = request.form.get('mode', 'signature')
        result['k'] = request.form.get('k', '2')
        result['adj_dir'] = request.form.get('adj_dir', default_adj_dir).strip()
        result['base_out'] = request.form.get('base_out', default_base_out).strip()
        result['hdfs_query_path'] = request.form.get('hdfs_query_path', default_hdfs_query_path).strip()
        action = request.form.get('action', 'draw_only')

        query_text = parse_query_form(result['nodes'], result['edges'], result['directed'])
        query_path = GENERATED_DIR / 'query.txt'
        query_path.write_text(query_text, encoding='utf-8')

        query_png = STATIC_DIR / 'query.png'
        render_graph(query_path, query_png)
        result['query_png'] = 'static/query.png'

        if action == 'draw_only':
            return render_template('index.html', result=result)

        try:
            hdfs_put_file(query_path, result['hdfs_query_path'])
        except Exception as e:
            result['error'] = f'Failed to upload GUI query to HDFS: {e}'
            return render_template('index.html', result=result)

        jar_path = default_jar_path

        try:
            if action == 'run_single':
                single_out = f"{result['base_out']}/single"
                metrics = run_pipeline_once(
                    result['adj_dir'],
                    result['hdfs_query_path'],
                    single_out,
                    result['mode'],
                    int(result['k']),
                    jar_path,
                )
                result['single_metrics'] = metrics
                result['stdout'] = metrics['stdout']
                if metrics['match_example']:
                    match_png = STATIC_DIR / 'match.png'
                    render_graph(query_path, match_png, highlight_nodes=set(metrics['match_example'].keys()))
                    result['match_png'] = 'static/match.png'

            elif action == 'run_compare':
                runs = []
                runs.append(run_pipeline_once(
                    result['adj_dir'],
                    result['hdfs_query_path'],
                    f"{result['base_out']}/baseline",
                    'baseline',
                    2,
                    jar_path,
                ))
                runs.append(run_pipeline_once(
                    result['adj_dir'],
                    result['hdfs_query_path'],
                    f"{result['base_out']}/signature_k1",
                    'signature',
                    1,
                    jar_path,
                ))
                runs.append(run_pipeline_once(
                    result['adj_dir'],
                    result['hdfs_query_path'],
                    f"{result['base_out']}/signature_k2",
                    'signature',
                    2,
                    jar_path,
                ))

                baseline_candidates = runs[0]['candidate_count']
                comparison_rows = []
                for row in runs:
                    label = 'Baseline' if row['mode'] == 'baseline' else f"Signature (k={row['k']})"
                    comparison_rows.append({
                        'label': label,
                        'k': '-' if row['mode'] == 'baseline' else row['k'],
                        'candidates': row['candidate_count'],
                        'matches': row['match_count'],
                        'runtime': row['cpu_time_sec'],
                        'candidate_reduction': 0 if row['mode'] == 'baseline' else candidate_reduction(baseline_candidates, row['candidate_count']),
                        'pruning_ratio': 0.0 if row['mode'] == 'baseline' else pruning_ratio(baseline_candidates, row['candidate_count']),
                        'match_example': row['match_example'],
                    })

                result['comparison_rows'] = comparison_rows
                result['stdout'] = "\n\n".join(r['stdout'] for r in runs if r.get('stdout'))

                # show the strongest signature example match image by default
                best = runs[-1]
                if best['match_example']:
                    match_png = STATIC_DIR / 'match.png'
                    render_graph(query_path, match_png, highlight_nodes=set(best['match_example'].keys()))
                    result['match_png'] = 'static/match.png'

        except Exception as e:
            result['error'] = str(e)

    return render_template('index.html', result=result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)