# How to clone, install, and run NeighborSig-Match on another Windows machine

This guide assumes you are starting from a **GitHub repository** that already contains the full project.

---

## Part 1. Install the required tools on Windows

### 1. Install WSL 2

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

Restart if Windows asks.

### 2. Open Ubuntu in WSL

After installation, open your Ubuntu terminal.

### 3. Install Java, Python, Git, and utility tools

```bash
sudo apt update
sudo apt install -y openjdk-11-jdk python3 python3-pip python3-venv python3-full git ssh rsync curl tar gzip unzip
```

### 4. Verify tools

```bash
java -version
git --version
python3 --version
```

---

## Part 2. Install Hadoop in WSL

### 1. Download Hadoop

```bash
cd ~
curl -O https://downloads.apache.org/hadoop/common/hadoop-3.4.3/hadoop-3.4.3.tar.gz
tar -xzf hadoop-3.4.3.tar.gz
mv hadoop-3.4.3 hadoop
```

### 2. Set environment variables

Add these lines to `~/.bashrc`:

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=$HOME/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
```

Reload the shell:

```bash
source ~/.bashrc
```

### 3. Configure Hadoop pseudo-distributed mode

Edit these files:

- `$HADOOP_HOME/etc/hadoop/core-site.xml`
- `$HADOOP_HOME/etc/hadoop/hdfs-site.xml`
- `$HADOOP_HOME/etc/hadoop/mapred-site.xml`
- `$HADOOP_HOME/etc/hadoop/yarn-site.xml`
- `$HADOOP_HOME/etc/hadoop/hadoop-env.sh`

Use these contents.

#### `hadoop-env.sh`

Make sure it contains:

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
```

#### `core-site.xml`

```xml
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://localhost:9000</value>
  </property>
</configuration>
```

#### `hdfs-site.xml`

```xml
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>1</value>
  </property>
</configuration>
```

#### `mapred-site.xml`

If the file does not exist, copy the template first:

```bash
cp $HADOOP_HOME/etc/hadoop/mapred-site.xml.template $HADOOP_HOME/etc/hadoop/mapred-site.xml
```

Then use:

```xml
<configuration>
  <property>
    <name>mapreduce.framework.name</name>
    <value>yarn</value>
  </property>
  <property>
    <name>mapreduce.application.classpath</name>
    <value>$HADOOP_MAPRED_HOME/share/hadoop/mapreduce/*:$HADOOP_MAPRED_HOME/share/hadoop/mapreduce/lib/*</value>
  </property>
</configuration>
```

#### `yarn-site.xml`

```xml
<configuration>
  <property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
  </property>
  <property>
    <name>yarn.nodemanager.env-whitelist</name>
    <value>JAVA_HOME,HADOOP_COMMON_HOME,HADOOP_HDFS_HOME,HADOOP_CONF_DIR,CLASSPATH_PREPEND_DISTCACHE,HADOOP_YARN_HOME,HADOOP_HOME,PATH,LANG,TZ,HADOOP_MAPRED_HOME</value>
  </property>
</configuration>
```

### 4. Enable passwordless SSH

```bash
ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
sudo service ssh start
ssh localhost
```

### 5. Format and start Hadoop

```bash
hdfs namenode -format
start-dfs.sh
start-yarn.sh
jps
```

You should see processes such as:

- NameNode
- DataNode
- ResourceManager
- NodeManager
- SecondaryNameNode

---

## Part 3. Clone the GitHub repository

Replace `YOUR_USERNAME` and `YOUR_REPO`.

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

Example:

```bash
git clone https://github.com/YOUR_USERNAME/neighbor-sig-match.git
cd neighbor-sig-match
```

---

## Part 4. Build the project

### 1. Compile the Java Hadoop jobs

```bash
bash scripts/compile.sh
```

This should create:

```text
dist/neighborsig-match.jar
```

### 2. Create the Python virtual environment for the GUI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-gui.txt
```

---

## Part 5. Prepare a dataset

### Option A: use the GUI later to upload a dataset

You can skip dataset preparation now and do it from the GUI.

### Option B: prepare one manually from the command line

Example with SNAP `ca-GrQc`:

```bash
mkdir -p ~/graphmatch_data
cd ~/graphmatch_data
curl -O https://snap.stanford.edu/data/ca-GrQc.txt.gz
```

Convert it:

```bash
cd ~/neighbor-sig-match
python3 scripts/snap_to_adjacency.py \
  --input ~/graphmatch_data/ca-GrQc.txt.gz \
  --output ~/graphmatch_data/ca-GrQc.adj \
  --num-labels 8
```

Put it into HDFS:

```bash
hdfs dfs -mkdir -p /projects/graphmatch/input/adj
hdfs dfs -mkdir -p /projects/graphmatch/input/queries
hdfs dfs -put -f ~/graphmatch_data/ca-GrQc.adj /projects/graphmatch/input/adj/part-00000
hdfs dfs -put -f queries/sample_query.txt /projects/graphmatch/input/queries/sample_query.txt
```

---

## Part 6. Run from the command line

```bash
bash scripts/run_pipeline.sh \
  /projects/graphmatch/input/adj \
  /projects/graphmatch/input/queries/sample_query.txt \
  /projects/graphmatch/output \
  signature \
  2 \
  dist/neighborsig-match.jar
```

Check outputs:

```bash
hdfs dfs -ls -R /projects/graphmatch/output
```

---

## Part 7. Run the GUI

From the project root:

```bash
cd ~/neighbor-sig-match
source .venv/bin/activate
export HDFS_ADJ_DIR=/projects/graphmatch/input/adj
export HDFS_BASE_OUTPUT=/projects/graphmatch/output/gui
export HADOOP_JAR=$PWD/dist/neighborsig-match.jar
export HDFS_GUI_QUERY_PATH=/projects/graphmatch/input/gui/query.txt
cd gui
python app.py
```

Open this in your browser:

```text
http://localhost:5000
```

---

## Part 8. What the GUI can do

The GUI can:

- enter a query graph
- run baseline, `k=1`, and `k=2`
- upload SNAP datasets
- build up to 3 subsets, for example `1000,2000,3000`
- select subsets from a dropdown
- run batch experiments across selected subsets
- show:
  - candidates
  - matches
  - pruning ratio
  - runtime
  - map output bytes
  - reduce shuffle bytes
- visualize one real example match
- export a history CSV

---

## Part 9. Typical shutdown and restart

### Stop GUI

Press `Ctrl + C` in the terminal running Flask.

### Stop Hadoop

```bash
stop-yarn.sh
stop-dfs.sh
```

### Start again later

```bash
source ~/.bashrc
start-dfs.sh
start-yarn.sh
cd ~/neighbor-sig-match
source .venv/bin/activate
export HDFS_ADJ_DIR=/projects/graphmatch/input/adj
export HDFS_BASE_OUTPUT=/projects/graphmatch/output/gui
export HADOOP_JAR=$PWD/dist/neighborsig-match.jar
export HDFS_GUI_QUERY_PATH=/projects/graphmatch/input/gui/query.txt
cd gui
python app.py
```

---

## Part 10. Troubleshooting

### Hadoop not starting

- Check `jps`
- Verify `JAVA_HOME`
- Verify SSH works with `ssh localhost`

### GUI cannot run Hadoop jobs

- Check `dist/neighborsig-match.jar` exists
- Check HDFS paths are correct
- Check Hadoop is running

### No results in HDFS

- Re-run the pipeline and inspect the terminal output
- Confirm the dataset exists in HDFS with `hdfs dfs -ls`

### Python package install issue

If you see the `externally-managed-environment` error, use the virtual environment exactly as shown above. Do not install GUI packages system-wide.
