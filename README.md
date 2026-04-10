# NeighborSig-Match

A Hadoop MapReduce reference implementation for the proposal **Distributed Subgraph Matching with Neighborhood-Signature Pruning on Large Graph Databases**.

This codebase is designed for a **Windows machine running Hadoop in WSL pseudo-distributed mode**. That gives you a Windows-hosted setup with the standard Linux commands used by Apache Hadoop's official single-node instructions.

---

## 1. What this system implements

### Core problem

Given:

- a **large labeled data graph** `G` in HDFS
- a **small labeled query graph** `q`

find every injective mapping `f : V(q) -> V(G)` such that node labels match and every query edge exists in the data graph with the same edge label.

### Main idea

Before full verification, each data node gets a **k-hop neighborhood signature**:

- `hop 1`: multiset of labels among immediate neighbors
- `hop 2`: multiset of labels among distinct 2-hop neighbors

A data node `v` can only be a candidate for query node `u` if:

1. `label(v) = label(u)`
2. `degree(v) >= degree(u)`
3. `Sig(u, k)` is **subsumed** by `Sig(v, k)` hop-by-hop

That pruning is the difference between:

- **baseline**: only degree + label filtering
- **proposed method**: degree + label + k-hop signature filtering

---

## 2. File formats

### 2.1 Data graph adjacency file

Each line:

```text
nodeId<TAB>nodeLabel<TAB>neighbor1:neighborLabel:edgeLabel,neighbor2:neighborLabel:edgeLabel,...
```

Example:

```text
1	L1	2:L2:E,5:L0:E
2	L2	1:L1:E,3:L3:E
3	L3	2:L2:E
```

### 2.2 Query graph file

Plain text format:

```text
directed=false
v q0 L0
v q1 L1
v q2 L2
e q0 q1 E
e q1 q2 E
```

### 2.3 Signature file

Produced by Job 1. Each reducer output line is:

```text
nodeId<TAB>nodeId<TAB>label<TAB>degree<TAB>neighborIdsCsv<TAB>hop1Multiset<TAB>hop2Multiset
```

The duplicate nodeId appears because Hadoop writes `key<TAB>value`, and the value itself starts with `nodeId`.

### 2.4 Candidate file

Produced by Job 2:

```text
queryNodeId<TAB>candidate1,candidate2,candidate3
```

### 2.5 Match file

Produced by Job 3:

```text
match-000001	q0=123,q1=456,q2=778
```

---

## 3. HDFS directory layout

Recommended layout:

```text
/projects/graphmatch/
  input/
    raw/
      ca-GrQc.txt.gz
    adj/
      part-00000
    queries/
      sample_query.txt
  output/
    signatures/
    candidates_baseline/
    candidates_signature/
    matches_baseline/
    matches_signature/
  tmp/
```

---

## 4. MapReduce pipeline

### Job 1: Signature Construction

**Input:** adjacency list in HDFS
**Output:** per-node signature index in HDFS

Mapper behavior:

- emits one `SELF` record for each node
- emits `TWOHOP` contributions to each neighbor using the current node's adjacency list

Reducer behavior:

- reconstructs the node's immediate neighbors
- builds hop-1 label multiset
- deduplicates 2-hop node ids
- excludes self and 1-hop nodes from the 2-hop multiset
- writes the signature record

### Job 2: Candidate Generation

**Input:** signature index
**Distributed Cache:** query graph
**Output:** candidate sets per query node

Mapper behavior:

- loads the query graph and computes query signatures in memory
- compares every data signature against every query node
- baseline mode uses only label + degree
- signature mode also applies multiset subsumption on hop-1 and hop-2

Reducer behavior:

- groups candidate data nodes by query node
- writes one candidate list per query node

### Job 3: Subgraph Verification

**Input:** adjacency list
**Distributed Cache:** query graph + candidate file
**Output:** verified matches only

Mapper behavior:

- loads the candidate universe from the cached candidate file
- emits adjacency rows only for data nodes that survive pruning

Reducer behavior:

- builds the candidate-induced adjacency map
- orders query nodes by smallest candidate set first
- runs exact backtracking search with injectivity and edge-label checks
- outputs only verified matches

> Note: for course-project scale, this reducer-centric verification is a practical compromise. It is exact, but it assumes the pruned candidate subgraph is small enough to fit on one reducer.

---

## 5. Distributed Cache usage

Distributed Cache is used in two places:

1. **Candidate Generation**

   - cache file: query graph
   - reason: query is tiny and should be present on every mapper
2. **Subgraph Verification**

   - cache files: query graph + candidate file
   - reason: mappers need the candidate universe, reducer needs full candidate sets

---

## 6. Windows-specific setup (recommended: WSL)

### Why WSL

Apache Hadoop's documented single-node flow is standard Linux shell configuration. Running Hadoop inside **WSL 2 on Windows** is the most reliable path for a Windows-hosted course project.

### Install WSL

In PowerShell as Administrator:

```powershell
wsl --install
```

Then open Ubuntu and install dependencies:

```bash
sudo apt update
sudo apt install -y openjdk-11-jdk ssh rsync curl tar gzip
java -version
```

### Download Hadoop

Inside WSL:

```bash
cd ~
curl -O https://downloads.apache.org/hadoop/common/hadoop-3.4.3/hadoop-3.4.3.tar.gz
tar -xzf hadoop-3.4.3.tar.gz
mv hadoop-3.4.3 hadoop
```

### Environment variables

Add to `~/.bashrc`:

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=$HOME/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
```

Reload shell:

```bash
source ~/.bashrc
```

### Configure pseudo-distributed Hadoop

Edit:

- `$HADOOP_HOME/etc/hadoop/core-site.xml`
- `$HADOOP_HOME/etc/hadoop/hdfs-site.xml`
- `$HADOOP_HOME/etc/hadoop/mapred-site.xml`
- `$HADOOP_HOME/etc/hadoop/yarn-site.xml`

Minimal configuration:

`core-site.xml`

```xml
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://localhost:9000</value>
  </property>
</configuration>
```

`hdfs-site.xml`

```xml
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>1</value>
  </property>
</configuration>
```

`mapred-site.xml`

```xml
<configuration>
  <property>
    <name>mapreduce.framework.name</name>
    <value>yarn</value>
  </property>
</configuration>
```

`yarn-site.xml`

```xml
<configuration>
  <property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
  </property>
</configuration>
```

Format NameNode once:

```bash
hdfs namenode -format
```

Start services:

```bash
start-dfs.sh
start-yarn.sh
jps
```

---

## 7. Dataset recommendation

### Best full-scale dataset for this project

Use **soc-Pokec** if you want one official SNAP source that can support your 10K / 100K / 1M-node experiments by sampling induced subgraphs.

Official file from SNAP:

- `soc-pokec-relationships.txt.gz`

### End-to-end smoke test dataset

Use **ca-GrQc** first, because it is small and easy to validate.

---

## 8. Download + preprocessing

### Example A: smoke test with ca-GrQc

```bash
mkdir -p ~/graphmatch_data
cd ~/graphmatch_data
curl -O https://snap.stanford.edu/data/ca-GrQc.txt.gz
gunzip -k ca-GrQc.txt.gz
```

Convert to adjacency list:

```bash
cd /path/to/neighbor-sig-match
python3 scripts/snap_to_adjacency.py \
  --input ~/graphmatch_data/ca-GrQc.txt.gz \
  --output ~/graphmatch_data/ca-GrQc.adj \
  --num-labels 8
```

### Example B: full-scale source with Pokec

```bash
mkdir -p ~/graphmatch_data
cd ~/graphmatch_data
curl -O https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz
```

Convert:

```bash
cd /path/to/neighbor-sig-match
python3 scripts/snap_to_adjacency.py \
  --input ~/graphmatch_data/soc-pokec-relationships.txt.gz \
  --output ~/graphmatch_data/soc-Pokec.adj \
  --directed \
  --num-labels 8
```

Create smaller induced subgraphs:

```bash
python3 scripts/sample_subgraph.py --input ~/graphmatch_data/soc-Pokec.adj --output ~/graphmatch_data/pokec_10k.adj --max-nodes 10000
python3 scripts/sample_subgraph.py --input ~/graphmatch_data/soc-Pokec.adj --output ~/graphmatch_data/pokec_100k.adj --max-nodes 100000
python3 scripts/sample_subgraph.py --input ~/graphmatch_data/soc-Pokec.adj --output ~/graphmatch_data/pokec_1m.adj --max-nodes 1000000
```

---

## 9. Put data into HDFS

```bash
hdfs dfs -mkdir -p /projects/graphmatch/input/raw
hdfs dfs -mkdir -p /projects/graphmatch/input/adj
hdfs dfs -mkdir -p /projects/graphmatch/input/queries

hdfs dfs -put -f ~/graphmatch_data/ca-GrQc.adj /projects/graphmatch/input/adj/part-00000
hdfs dfs -put -f queries/sample_query.txt /projects/graphmatch/input/queries/sample_query.txt
```

---

## 10. Compile

Inside WSL, from project root:

```bash
bash scripts/compile.sh
```

Equivalent manual compile commands:

```bash
mkdir -p build/classes dist
javac -cp "$(hadoop classpath)" -d build/classes $(find src/main/java -name '*.java')
jar -cvf dist/neighborsig-match.jar -C build/classes .
```

---

## 11. Run each job manually

### Job 1: Signature Construction

```bash
hdfs dfs -rm -r -f /projects/graphmatch/output/signatures
hadoop jar dist/neighborsig-match.jar edu.kent.cs730.graphmatch.jobs.signature.SignatureConstructionDriver \
  /projects/graphmatch/input/adj \
  /projects/graphmatch/output/signatures
```

### Job 2A: Baseline candidate generation

```bash
hdfs dfs -rm -r -f /projects/graphmatch/output/candidates_baseline
hadoop jar dist/neighborsig-match.jar edu.kent.cs730.graphmatch.jobs.candidate.CandidateGenerationDriver \
  /projects/graphmatch/output/signatures \
  /projects/graphmatch/input/queries/sample_query.txt \
  /projects/graphmatch/output/candidates_baseline \
  baseline \
  2
```

### Job 2B: Signature candidate generation

```bash
hdfs dfs -rm -r -f /projects/graphmatch/output/candidates_signature
hadoop jar dist/neighborsig-match.jar edu.kent.cs730.graphmatch.jobs.candidate.CandidateGenerationDriver \
  /projects/graphmatch/output/signatures \
  /projects/graphmatch/input/queries/sample_query.txt \
  /projects/graphmatch/output/candidates_signature \
  signature \
  2
```

### Job 3A: Verify baseline candidates

```bash
hdfs dfs -rm -r -f /projects/graphmatch/output/matches_baseline
hadoop jar dist/neighborsig-match.jar edu.kent.cs730.graphmatch.jobs.verify.SubgraphVerificationDriver \
  /projects/graphmatch/input/adj \
  /projects/graphmatch/input/queries/sample_query.txt \
  /projects/graphmatch/output/candidates_baseline/part-r-00000 \
  /projects/graphmatch/output/matches_baseline
```

### Job 3B: Verify signature candidates

```bash
hdfs dfs -rm -r -f /projects/graphmatch/output/matches_signature
hadoop jar dist/neighborsig-match.jar edu.kent.cs730.graphmatch.jobs.verify.SubgraphVerificationDriver \
  /projects/graphmatch/input/adj \
  /projects/graphmatch/input/queries/sample_query.txt \
  /projects/graphmatch/output/candidates_signature/part-r-00000 \
  /projects/graphmatch/output/matches_signature
```

### One-command pipeline

```bash
bash scripts/run_pipeline.sh \
  /projects/graphmatch/input/adj \
  /projects/graphmatch/input/queries/sample_query.txt \
  /projects/graphmatch/output \
  signature \
  2 \
  dist/neighborsig-match.jar
```

---

## 12. GUI

Install Python packages:

```bash
pip install flask networkx matplotlib
```

Set environment variables:

```bash
export HDFS_ADJ_DIR=/projects/graphmatch/input/adj
export HDFS_BASE_OUTPUT=/projects/graphmatch/output/gui
export HADOOP_JAR=$(pwd)/dist/neighborsig-match.jar
```

Run GUI:

```bash
python3 gui/app.py
```

Open:

```text
http://127.0.0.1:5000
```

GUI features included:

- node/edge text input for query specification
- baseline vs signature mode toggle
- k selection
- button to launch matching
- metrics panel with CPU time, candidate count, and match count
- graph rendering with NetworkX + Matplotlib

---

## 13. Experiments

### Baseline vs proposed system

- **Baseline:** degree + label filtering only
- **Proposed:** degree + label + k-hop neighborhood signature pruning

### Suggested experimental matrix

- graph size: 10K, 100K, 1M nodes
- query size: 5, 10, 15, 20 nodes
- k: 1 and 2
- nodes in cluster: 1, 2, 4 logical workers if available

### Metrics to record

- total job CPU time in seconds
- candidate count after pruning
- pruning ratio
- bytes shuffled from Hadoop counters/logs
- valid matches found

### Helper script

```bash
python3 experiments/run_experiments.py \
  --adj-dir /projects/graphmatch/input/adj \
  --query-file /projects/graphmatch/input/queries/sample_query.txt \
  --base-output /projects/graphmatch/output/exp1 \
  --k 2 \
  --jar dist/neighborsig-match.jar \
  --csv exp1_results.csv
```

---

## 14. Expected result shape

You should expect these trends:

- signature mode emits fewer candidates than baseline
- `k=2` usually prunes more aggressively than `k=1`
- verification time improves most when query size grows
- shuffle volume should drop when candidate emission drops
- final match count must match the baseline exactly

---

## 15. Common debugging issues

### Hadoop not starting

Check:

```bash
jps
hdfs dfs -ls /
```

Typical fixes:

- `JAVA_HOME` not exported
- NameNode not formatted
- stale PID files after abrupt stop
- rerun `start-dfs.sh` and `start-yarn.sh`

### `ClassNotFoundException`

Typical causes:

- wrong fully-qualified class name in `hadoop jar`
- jar built without compiled classes
- compiling without `$(hadoop classpath)`

### Wrong output or zero matches

Check these first:

- query labels actually exist in the dataset
- baseline mode still returns candidates
- adjacency file format is exactly `nodeId<TAB>label<TAB>...`
- undirected data was actually converted with symmetric edges
- query edge labels match data edge labels

### Out-of-memory or reducer bottleneck

This code does exact verification on one reducer after pruning. Fixes:

- run smaller query first
- reduce label cardinality mismatch issues in synthetic labels
- use `k=2` to prune harder
- test on 10K or 100K first
- increase reducer heap in Hadoop config if needed

---

## 16. Limits of this reference implementation

This implementation is intentionally **complete and runnable**, but it is still a course-project reference design, not a production engine.

The main simplifications are:

1. verification is centralized to one reducer after candidate pruning
2. communication-overhead reporting is taken from Hadoop counters/logs, not custom instrumentation
3. unlabeled SNAP datasets are converted into labeled graphs with deterministic synthetic node labels

Those choices keep the implementation realistic enough to run and evaluate, while still matching the proposal's algorithmic intent.
