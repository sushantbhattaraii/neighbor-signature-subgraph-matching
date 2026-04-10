#!/usr/bin/env python3
import csv
import os
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, send_file
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
STATIC_DIR = APP_ROOT / 'static'
GENERATED_DIR = APP_ROOT / 'generated'
UPLOADS_DIR = APP_ROOT / 'uploads'
HISTORY_CSV = GENERATED_DIR / 'run_history.csv'

for d in [STATIC_DIR, GENERATED_DIR, UPLOADS_DIR]:
    d.mkdir(exist_ok=True)

app = Flask(__name__)


def sanitize_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[^A-Za-z0-9._-]+', '_', text)
    return text or 'dataset'


def parse_subset_sizes(text: str):
    text = (text or '').strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split(',') if p.strip()]
    if len(parts) > 3:
        raise ValueError('Please provide at most 3 subset sizes, separated by commas.')
    sizes = []
    for p in parts:
        value = int(p)
        if value <= 0:
            raise ValueError('Subset sizes must be positive integers.')
        sizes.append(value)
    if len(set(sizes)) != len(sizes):
        raise ValueError('Subset sizes must be unique.')
    return sizes


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


def render_query_graph(query_path: Path, output_png: Path, highlight_nodes=None):
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


def ensure_history_header():
    if HISTORY_CSV.exists():
        return
    with open(HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'dataset_hdfs_dir', 'query_nodes', 'method', 'k',
            'candidates', 'matches', 'candidate_reduction', 'pruning_ratio', 'runtime_sec'
        ])


def append_history_row(row):
    ensure_history_header()
    with open(HISTORY_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(row)


def load_history(limit=20):
    if not HISTORY_CSV.exists():
        return []
    rows = []
    with open(HISTORY_CSV, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    rows.reverse()
    return rows[:limit]


def count_query_nodes(nodes_text: str) -> int:
    return len([x for x in nodes_text.splitlines() if x.strip()])


def preprocess_and_upload_dataset(file_storage, dataset_name, dataset_directed, num_labels, subset_sizes, adj_dir):
    safe_name = sanitize_name(dataset_name or Path(file_storage.filename).stem)
    upload_path = UPLOADS_DIR / file_storage.filename
    file_storage.save(upload_path)

    converted_path = GENERATED_DIR / f'{safe_name}.adj'
    convert_cmd = [
        'python', str(PROJECT_ROOT / 'scripts' / 'snap_to_adjacency.py'),
        '--input', str(upload_path),
        '--output', str(converted_path),
        '--num-labels', str(num_labels),
    ]
    if dataset_directed:
        convert_cmd.append('--directed')

    proc = run_cmd(convert_cmd, cwd=PROJECT_ROOT)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)

    created_targets = []

    # upload full converted dataset to the selected main adjacency dir
    full_hdfs_target = f"{adj_dir.rstrip('/')}/part-00000"
    hdfs_put_file(converted_path, full_hdfs_target)
    created_targets.append({
        'label': 'full',
        'nodes': 'full',
        'local_processed_file': str(converted_path),
        'hdfs_dir': adj_dir.rstrip('/'),
        'hdfs_target': full_hdfs_target,
    })

    for size in subset_sizes:
        subset_path = GENERATED_DIR / f'{safe_name}_{size}.adj'
        sample_cmd = [
            'python', str(PROJECT_ROOT / 'scripts' / 'sample_subgraph.py'),
            '--input', str(converted_path),
            '--output', str(subset_path),
            '--max-nodes', str(size),
        ]
        proc2 = run_cmd(sample_cmd, cwd=PROJECT_ROOT)
        if proc2.returncode != 0:
            raise RuntimeError(proc2.stderr or proc2.stdout)

        subset_hdfs_dir = f"{adj_dir.rstrip('/')}_{size}"
        subset_hdfs_target = f"{subset_hdfs_dir}/part-00000"
        hdfs_put_file(subset_path, subset_hdfs_target)

        created_targets.append({
            'label': f'subset_{size}',
            'nodes': size,
            'local_processed_file': str(subset_path),
            'hdfs_dir': subset_hdfs_dir,
            'hdfs_target': subset_hdfs_target,
        })

    return {
        'local_uploaded_file': str(upload_path),
        'created_targets': created_targets,
    }


def load_adjacency_from_hdfs(adj_dir: str):
    data = hdfs_cat(f"{adj_dir.rstrip('/')}/part-00000")
    if not data.strip():
        raise RuntimeError(f"Could not read adjacency file from {adj_dir}/part-00000")

    adj = {}
    labels = {}
    edge_labels = defaultdict(dict)

    for raw in data.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        node_id = parts[0]
        node_label = parts[1]
        nbrs = parts[2]

        labels[node_id] = node_label
        adj[node_id] = set()

        if nbrs != '-':
            for tok in nbrs.split(','):
                sub = tok.split(':')
                if len(sub) >= 3:
                    nbr_id, nbr_label, e_label = sub[0], sub[1], sub[2]
                elif len(sub) == 2:
                    nbr_id, nbr_label = sub[0], sub[1]
                    e_label = 'E'
                else:
                    nbr_id = sub[0]
                    nbr_label = '?'
                    e_label = 'E'
                adj[node_id].add(nbr_id)
                edge_labels[node_id][nbr_id] = e_label
                labels.setdefault(nbr_id, nbr_label)

    return adj, labels, edge_labels


def render_real_match_context(adj_dir: str, mapping: dict, output_png: Path):
    adj, labels, edge_labels = load_adjacency_from_hdfs(adj_dir)

    matched_nodes = set(mapping.values())
    context_nodes = set(matched_nodes)

    for n in list(matched_nodes):
        for nbr in adj.get(n, set()):
            context_nodes.add(nbr)

    G = nx.Graph()

    for n in context_nodes:
        G.add_node(n, label=labels.get(n, '?'), matched=(n in matched_nodes))

    for src in context_nodes:
        for dst in adj.get(src, set()):
            if dst in context_nodes and src <= dst:
                is_match_edge = (src in matched_nodes and dst in matched_nodes)
                label = edge_labels.get(src, {}).get(dst, edge_labels.get(dst, {}).get(src, 'E'))
                G.add_edge(src, dst, label=label, matched=is_match_edge)

    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(G, seed=7)

    node_colors = []
    node_sizes = []
    for n in G.nodes():
        if n in matched_nodes:
            node_colors.append('orange')
            node_sizes.append(1400)
        else:
            node_colors.append('lightgray')
            node_sizes.append(800)

    edge_colors = []
    widths = []
    for u, v in G.edges():
        if G.edges[u, v].get('matched'):
            edge_colors.append('red')
            widths.append(2.8)
        else:
            edge_colors.append('gray')
            widths.append(1.2)

    nx.draw(
        G, pos,
        with_labels=True,
        node_color=node_colors,
        node_size=node_sizes,
        edge_color=edge_colors,
        width=widths,
        font_size=8
    )
    nx.draw_networkx_labels(
        G, pos,
        labels={n: f"{n}\n{G.nodes[n].get('label','')}" for n in G.nodes()},
        font_size=8
    )

    edge_label_subset = {}
    for u, v in G.edges():
        if G.edges[u, v].get('matched'):
            edge_label_subset[(u, v)] = G.edges[u, v].get('label', 'E')
    if edge_label_subset:
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_label_subset, font_size=8)

    plt.title('Example Match Highlighted in Original Graph Context')
    plt.tight_layout()
    plt.savefig(output_png, bbox_inches='tight')
    plt.close()


@app.route('/history.csv')
def history_csv():
    ensure_history_header()
    return send_file(HISTORY_CSV, as_attachment=True, download_name='run_history.csv')


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
        'dataset_name': 'uploaded_dataset',
        'dataset_directed': False,
        'num_labels': '8',
        'subset_sizes': '1000,2000,3000',
        'query_png': None,
        'match_png': None,
        'single_metrics': None,
        'comparison_rows': None,
        'upload_status': None,
        'error': None,
        'stdout': None,
        'history_rows': load_history(),
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
        result['dataset_name'] = request.form.get('dataset_name', 'uploaded_dataset').strip()
        result['dataset_directed'] = request.form.get('dataset_directed') == 'on'
        result['num_labels'] = request.form.get('num_labels', '8').strip()
        result['subset_sizes'] = request.form.get('subset_sizes', '1000,2000,3000').strip()
        action = request.form.get('action', 'draw_only')

        query_text = parse_query_form(result['nodes'], result['edges'], result['directed'])
        query_path = GENERATED_DIR / 'query.txt'
        query_path.write_text(query_text, encoding='utf-8')

        query_png = STATIC_DIR / 'query.png'
        render_query_graph(query_path, query_png)
        result['query_png'] = 'static/query.png'

        if action == 'draw_only':
            return render_template('index.html', result=result)

        if action == 'upload_dataset':
            try:
                file_storage = request.files.get('dataset_file')
                if not file_storage or not file_storage.filename:
                    raise RuntimeError('Please choose a dataset file first.')
                subset_sizes = parse_subset_sizes(result['subset_sizes'])
                upload_info = preprocess_and_upload_dataset(
                    file_storage=file_storage,
                    dataset_name=result['dataset_name'],
                    dataset_directed=result['dataset_directed'],
                    num_labels=int(result['num_labels']),
                    subset_sizes=subset_sizes,
                    adj_dir=result['adj_dir'],
                )
                result['upload_status'] = upload_info
                result['history_rows'] = load_history()
                return render_template('index.html', result=result)
            except Exception as e:
                result['error'] = str(e)
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
                    render_real_match_context(result['adj_dir'], metrics['match_example'], match_png)
                    result['match_png'] = 'static/match.png'

                append_history_row([
                    datetime.now().isoformat(timespec='seconds'),
                    result['adj_dir'],
                    count_query_nodes(result['nodes']),
                    metrics['mode'],
                    metrics['k'],
                    metrics['candidate_count'],
                    metrics['match_count'],
                    '',
                    '',
                    metrics['cpu_time_sec'],
                ])

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
                    reduction = 0 if row['mode'] == 'baseline' else candidate_reduction(baseline_candidates, row['candidate_count'])
                    ratio = 0.0 if row['mode'] == 'baseline' else pruning_ratio(baseline_candidates, row['candidate_count'])
                    comparison_rows.append({
                        'label': label,
                        'k': '-' if row['mode'] == 'baseline' else row['k'],
                        'candidates': row['candidate_count'],
                        'matches': row['match_count'],
                        'runtime': row['cpu_time_sec'],
                        'candidate_reduction': reduction,
                        'pruning_ratio': ratio,
                        'match_example': row['match_example'],
                    })

                    append_history_row([
                        datetime.now().isoformat(timespec='seconds'),
                        result['adj_dir'],
                        count_query_nodes(result['nodes']),
                        row['mode'],
                        row['k'],
                        row['candidate_count'],
                        row['match_count'],
                        reduction,
                        ratio,
                        row['cpu_time_sec'],
                    ])

                result['comparison_rows'] = comparison_rows
                result['stdout'] = "\n\n".join(r['stdout'] for r in runs if r.get('stdout'))

                best = runs[-1]
                if best['match_example']:
                    match_png = STATIC_DIR / 'match.png'
                    render_real_match_context(result['adj_dir'], best['match_example'], match_png)
                    result['match_png'] = 'static/match.png'

            result['history_rows'] = load_history()

        except Exception as e:
            result['error'] = str(e)

    return render_template('index.html', result=result)


if __name__ == '__main__':
    app.run(debug=True, port=5000)