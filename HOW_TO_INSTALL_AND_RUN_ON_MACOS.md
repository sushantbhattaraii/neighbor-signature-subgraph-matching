# How to Install and Run NeighborSig-Match on macOS

This guide shows how to clone, install, and run the full **NeighborSig-Match** project on a macOS machine.

It assumes you want to run:
- the **Java Hadoop MapReduce backend**
- the **Flask GUI**
- a **single-node pseudo-distributed Hadoop setup** for local development and demos

---

## 0. What this project needs

The project needs all of the following:

- **Homebrew** for package management
- **Java 11** for Hadoop and the Java codebase
- **Python 3** for the GUI and preprocessing scripts
- **Git** to clone the repository
- **SSH enabled on localhost** because Hadoop’s start scripts expect SSH access
- **Apache Hadoop** installed locally in pseudo-distributed mode

This guide uses:
- **Hadoop 3.4.3**
- **OpenJDK 11**
- **Python virtual environment (`venv`)**

---

## 1. Before you begin

### 1.1 Check your macOS version
This guide assumes a currently supported Homebrew installation. If you are on an older macOS release, some Homebrew packages may not install cleanly.

### 1.2 Install Xcode Command Line Tools
Open **Terminal** and run:

```bash
xcode-select --install
```

If macOS says the tools are already installed, continue.

---

## 2. Install Homebrew

If Homebrew is not already installed, run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installation, run the shell commands Homebrew prints on screen. Then verify:

```bash
brew --version
```

---

## 3. Install required packages

Install Java 11, Python, Git, and a few utilities:

```bash
brew install openjdk@11 python git wget
```

Verify:

```bash
brew --prefix openjdk@11
python3 --version
git --version
```

---

## 4. Make Java 11 visible to macOS tools

Homebrew installs `openjdk@11` as a **keg-only** formula. The easiest clean setup is:

```bash
sudo ln -sfn "$(brew --prefix openjdk@11)/libexec/openjdk.jdk" /Library/Java/JavaVirtualMachines/openjdk-11.jdk
```

Then add Java 11 to your shell configuration.

### If you use zsh (default on modern macOS)

```bash
nano ~/.zshrc
```

Add:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 11)
export PATH="$JAVA_HOME/bin:$PATH"
```

Then reload:

```bash
source ~/.zshrc
```

### If you use bash

```bash
nano ~/.bash_profile
```

Add:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 11)
export PATH="$JAVA_HOME/bin:$PATH"
```

Then reload:

```bash
source ~/.bash_profile
```

Verify:

```bash
java -version
javac -version
echo $JAVA_HOME
```

You should see Java 11.

---

## 5. Enable Remote Login (SSH) on your Mac

Hadoop’s start scripts expect `ssh` to work on `localhost` without prompting for a password every time.

### 5.1 Turn on Remote Login in macOS

On your Mac:

1. Open **System Settings**
2. Go to **General**
3. Open **Sharing**
4. Turn on **Remote Login**
5. Allow access for your user account

### 5.2 Set up passwordless SSH to localhost

In Terminal, run:

```bash
ssh localhost
```

If it asks for a password or does not work passwordlessly, do this:

```bash
ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Now test again:

```bash
ssh localhost
```

If this connects to your own machine without asking for a password repeatedly, you are ready.

Exit the SSH session with:

```bash
exit
```

---

## 6. Install Apache Hadoop

Go to your home directory:

```bash
cd ~
```

Download Hadoop 3.4.3:

```bash
curl -O https://downloads.apache.org/hadoop/common/hadoop-3.4.3/hadoop-3.4.3.tar.gz
```

Extract it:

```bash
tar -xzf hadoop-3.4.3.tar.gz
mv hadoop-3.4.3 hadoop
```

---

## 7. Configure Hadoop environment variables

### If you use zsh

```bash
nano ~/.zshrc
```

Add:

```bash
export HADOOP_HOME=$HOME/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PATH="$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin"
```

Reload:

```bash
source ~/.zshrc
```

### If you use bash

```bash
nano ~/.bash_profile
```

Add:

```bash
export HADOOP_HOME=$HOME/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PATH="$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin"
```

Reload:

```bash
source ~/.bash_profile
```

Verify:

```bash
echo $HADOOP_HOME
hadoop version
```

---

## 8. Configure Hadoop for pseudo-distributed mode

Go to the Hadoop config directory:

```bash
cd $HADOOP_HOME/etc/hadoop
```

### 8.1 Set Java in `hadoop-env.sh`

Open:

```bash
nano hadoop-env.sh
```

Find or add:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 11)
```

If shell substitution causes trouble in your setup, replace it with the resolved path shown by:

```bash
/usr/libexec/java_home -v 11
```

Example:

```bash
export JAVA_HOME=/Library/Java/JavaVirtualMachines/openjdk-11.jdk/Contents/Home
```

---

### 8.2 Edit `core-site.xml`

```bash
nano core-site.xml
```

Replace its contents with:

```xml
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://localhost:9000</value>
  </property>
</configuration>
```

---

### 8.3 Edit `hdfs-site.xml`

```bash
nano hdfs-site.xml
```

Replace its contents with:

```xml
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>1</value>
  </property>
  <property>
    <name>dfs.namenode.name.dir</name>
    <value>file:///Users/YOUR_MAC_USERNAME/hadoopdata/hdfs/namenode</value>
  </property>
  <property>
    <name>dfs.datanode.data.dir</name>
    <value>file:///Users/YOUR_MAC_USERNAME/hadoopdata/hdfs/datanode</value>
  </property>
</configuration>
```

Replace `YOUR_MAC_USERNAME` with your macOS username.

Create those folders:

```bash
mkdir -p ~/hadoopdata/hdfs/namenode
mkdir -p ~/hadoopdata/hdfs/datanode
```

---

### 8.4 Create `mapred-site.xml`

If the file does not exist but `mapred-site.xml.template` does, copy it first:

```bash
cp mapred-site.xml.template mapred-site.xml
```

Then edit it:

```bash
nano mapred-site.xml
```

Replace its contents with:

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

---

### 8.5 Edit `yarn-site.xml`

```bash
nano yarn-site.xml
```

Replace its contents with:

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

---

## 9. Format HDFS and start Hadoop

### 9.1 Format the NameNode

```bash
hdfs namenode -format
```

### 9.2 Start HDFS

```bash
start-dfs.sh
```

### 9.3 Start YARN

```bash
start-yarn.sh
```

### 9.4 Verify processes

```bash
jps
```

You should see processes like:

- `NameNode`
- `DataNode`
- `SecondaryNameNode`
- `ResourceManager`
- `NodeManager`

If these are visible, Hadoop is up.

---

## 10. Create HDFS working folders

Run:

```bash
hdfs dfs -mkdir -p /user/$USER
hdfs dfs -mkdir -p /projects/graphmatch/input/adj
hdfs dfs -mkdir -p /projects/graphmatch/input/gui
hdfs dfs -mkdir -p /projects/graphmatch/output
```

Verify:

```bash
hdfs dfs -ls /
```

---

## 11. Clone the GitHub repository

Choose a folder where you want the project:

```bash
cd ~
```

Clone the repo:

```bash
git clone https://github.com/YOUR_USERNAME/neighbor-sig-match.git
cd neighbor-sig-match
```

Verify the project files are there:

```bash
ls
```

You should see folders such as:

- `src`
- `gui`
- `scripts`
- `queries`
- `dist` (after compilation)

---

## 12. Build the Java project

From the project root:

```bash
bash scripts/compile.sh
```

When successful, verify:

```bash
ls dist
```

You should see:

```text
neighborsig-match.jar
```

---

## 13. Set up the Python virtual environment for the GUI

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-gui.txt
```

Verify Flask is installed:

```bash
python -c "import flask; print(flask.__version__)"
```

---

## 14. Start the GUI

From the project root:

```bash
source .venv/bin/activate
export HDFS_ADJ_DIR=/projects/graphmatch/input/adj
export HDFS_BASE_OUTPUT=/projects/graphmatch/output/gui
export HADOOP_JAR=$PWD/dist/neighborsig-match.jar
export HDFS_GUI_QUERY_PATH=/projects/graphmatch/input/gui/query.txt
cd gui
python app.py
```

Now open this in your browser:

```text
http://localhost:5000
```

If the GUI starts successfully, you are ready to use the project.

---

## 15. First-time usage flow in the GUI

A simple recommended flow is:

### 15.1 Upload a dataset
In the GUI:
- use the **Dataset upload and subset generation** section
- choose a SNAP edge-list file, such as `ca-GrQc.txt.gz`
- set a dataset name
- set number of labels, for example `8`
- optionally enter subset sizes such as:

```text
1000,2000,3000
```

Then click:

```text
Upload + Convert + Build Subsets
```

The GUI will:
- convert the SNAP file into the project adjacency format
- upload the full adjacency dataset into HDFS
- create up to 3 subset adjacency datasets
- register them in the GUI

### 15.2 Select a dataset or subset
Use the dropdown in the **Hadoop / HDFS paths** section.

### 15.3 Enter a query graph
Example:

**Nodes**

```text
q0,L0
q1,L1
q2,L2
```

**Edges**

```text
q0,q1,E
q1,q2,E
```

### 15.4 Run the experiment
You can use:

- **Run Selected** for one method
- **Run All: Baseline + k=1 + k=2** for one selected dataset
- **Run Batch on Selected Subsets** for up to 3 subsets

The GUI will show:
- candidates
- matches
- pruning ratio
- runtime
- map output bytes
- reduce shuffle bytes
- an example matched subgraph visualization

---

## 16. How to stop everything

### Stop the GUI
In the terminal where the Flask app is running:

```bash
Ctrl + C
```

### Stop Hadoop

```bash
stop-yarn.sh
stop-dfs.sh
```

---

## 17. How to start everything next time

Every time you come back to the project:

### 17.1 Start Hadoop

```bash
source ~/.zshrc   # or source ~/.bash_profile
start-dfs.sh
start-yarn.sh
jps
```

### 17.2 Start the GUI

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

Open:

```text
http://localhost:5000
```

---

## 18. Troubleshooting

### Problem: `java -version` is not Java 11
Run:

```bash
/usr/libexec/java_home -v 11
```

Then re-check your shell file (`~/.zshrc` or `~/.bash_profile`) and make sure `JAVA_HOME` points to Java 11.

---

### Problem: `start-dfs.sh` or `start-yarn.sh` fails
Check:

```bash
ssh localhost
```

If SSH is not passwordless, repeat the SSH key steps in Section 5.

---

### Problem: `jps` does not show Hadoop daemons
Re-run:

```bash
hdfs namenode -format
start-dfs.sh
start-yarn.sh
```

Also inspect logs:

```bash
ls $HADOOP_HOME/logs
```

---

### Problem: GUI loads but experiments fail
Check that these environment variables are set in the terminal where you started Flask:

```bash
echo $HDFS_ADJ_DIR
echo $HDFS_BASE_OUTPUT
echo $HADOOP_JAR
echo $HDFS_GUI_QUERY_PATH
```

Also confirm the JAR exists:

```bash
ls ~/neighbor-sig-match/dist
```

---

### Problem: HDFS cannot find your adjacency data
Check:

```bash
hdfs dfs -ls /projects/graphmatch/input
hdfs dfs -ls /projects/graphmatch/input/adj
```

---

### Problem: Port 5000 is already in use
Start the GUI after changing the port in `gui/app.py`, or kill the old Flask process.

---

## 19. Recommended final check

After setup, verify all of these work:

```bash
java -version
hadoop version
jps
hdfs dfs -ls /
cd ~/neighbor-sig-match && bash scripts/compile.sh
```

Then start the GUI and confirm:

```text
http://localhost:5000
```

If all of that works, the project is installed correctly on your Mac.

---

## 20. Official references used for this guide

- Apache Hadoop Single Node / Pseudo-Distributed Setup: https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/SingleCluster.html
- Homebrew installation docs: https://docs.brew.sh/Installation
- Homebrew `openjdk@11` formula: https://formulae.brew.sh/formula/openjdk@11
- Python virtual environments (`venv`): https://docs.python.org/3/library/venv.html
- Apple Remote Login / SSH on macOS: https://support.apple.com/en-kz/guide/mac-help/mchlp1066/mac
