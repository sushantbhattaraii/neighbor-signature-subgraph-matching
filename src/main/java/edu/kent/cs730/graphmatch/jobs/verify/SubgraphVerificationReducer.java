package edu.kent.cs730.graphmatch.jobs.verify;

import edu.kent.cs730.graphmatch.model.AdjacencyEntry;
import edu.kent.cs730.graphmatch.model.DataNodeRecord;
import edu.kent.cs730.graphmatch.model.QueryGraph;
import edu.kent.cs730.graphmatch.util.CandidateFileUtils;
import edu.kent.cs730.graphmatch.util.QueryLoader;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class SubgraphVerificationReducer extends Reducer<IntWritable, Text, Text, Text> {
    enum VerificationCounters {
        CANDIDATE_SUBGRAPH_NODES,
        BACKTRACK_STATES,
        VERIFIED_MATCHES
    }

    private QueryGraph queryGraph;
    private Map<String, Set<String>> candidateSets;
    private Map<String, DataNodeRecord> candidateAdjacency;
    private List<String> queryOrder;
    private final Text outKey = new Text();
    private final Text outVal = new Text();
    private long matchCounter = 0L;

    // progress heartbeat support
    private long localBacktrackStates = 0L;
    private static final long PROGRESS_INTERVAL = 10000L;

    // cache neighbor -> edge-label maps to avoid rebuilding them repeatedly
    private final Map<String, Map<String, String>> edgeLabelCache = new HashMap<>();

    @Override
    protected void setup(Context context) throws IOException {
        URI[] cacheFiles = context.getCacheFiles();
        if (cacheFiles == null || cacheFiles.length < 2) {
            throw new IOException("Query file and candidate file must be in Distributed Cache.");
        }
        queryGraph = QueryLoader.loadFromUri(cacheFiles[0]);
        candidateSets = CandidateFileUtils.loadCandidateSets(Paths.get(cacheFiles[1].getPath()));
        candidateAdjacency = new HashMap<>();
        queryOrder = queryGraph.sortNodesForJoin(candidateSets);
    }

    @Override
    protected void reduce(IntWritable key, Iterable<Text> values, Context context) throws IOException, InterruptedException {
        for (Text value : values) {
            DataNodeRecord record = DataNodeRecord.parseLine(value.toString());
            candidateAdjacency.put(record.getNodeId(), record);
            edgeLabelCache.put(record.getNodeId(), buildNeighborEdgeLabelMap(record));
        }
        context.getCounter(VerificationCounters.CANDIDATE_SUBGRAPH_NODES).increment(candidateAdjacency.size());

        for (String queryNode : queryGraph.getNodeIds()) {
            if (candidateSets.getOrDefault(queryNode, Collections.emptySet()).isEmpty()) {
                return;
            }
        }

        backtrack(0, new LinkedHashMap<>(), new HashSet<>(), context);
    }

    private void backtrack(int depth,
                           Map<String, String> assignment,
                           Set<String> usedDataNodes,
                           Context context) throws IOException, InterruptedException {
        context.getCounter(VerificationCounters.BACKTRACK_STATES).increment(1);
        localBacktrackStates++;

        if (localBacktrackStates % PROGRESS_INTERVAL == 0) {
            context.setStatus("Verification backtracking states=" + localBacktrackStates + ", matches=" + matchCounter);
            context.progress();
        }

        if (depth == queryOrder.size()) {
            matchCounter++;
            context.getCounter(VerificationCounters.VERIFIED_MATCHES).increment(1);
            outKey.set(String.format("match-%06d", matchCounter));
            outVal.set(formatAssignment(assignment));
            context.setStatus("Verified matches=" + matchCounter);
            context.progress();
            context.write(outKey, outVal);
            return;
        }

        String queryNode = queryOrder.get(depth);
        for (String dataNode : candidateSets.getOrDefault(queryNode, Collections.emptySet())) {
            if (usedDataNodes.contains(dataNode)) {
                continue;
            }
            DataNodeRecord dataRecord = candidateAdjacency.get(dataNode);
            if (dataRecord == null) {
                continue;
            }
            if (!queryGraph.getNodeLabel(queryNode).equals(dataRecord.getNodeLabel())) {
                continue;
            }
            if (dataRecord.getDegree() < queryGraph.degree(queryNode)) {
                continue;
            }
            if (!isConsistent(queryNode, dataRecord, assignment)) {
                continue;
            }
            assignment.put(queryNode, dataNode);
            usedDataNodes.add(dataNode);
            backtrack(depth + 1, assignment, usedDataNodes, context);
            usedDataNodes.remove(dataNode);
            assignment.remove(queryNode);
        }
    }

    private boolean isConsistent(String queryNode,
                                 DataNodeRecord dataRecord,
                                 Map<String, String> currentAssignment) {
        Map<String, String> dataNeighborEdgeLabels =
        edgeLabelCache.computeIfAbsent(dataRecord.getNodeId(), k -> buildNeighborEdgeLabelMap(dataRecord));
        for (String assignedQueryNode : currentAssignment.keySet()) {
            String assignedDataNode = currentAssignment.get(assignedQueryNode);
            boolean queryForward = queryGraph.hasEdge(queryNode, assignedQueryNode);
            boolean queryBackward = queryGraph.hasEdge(assignedQueryNode, queryNode);

            if (queryForward) {
                String expectedEdgeLabel = queryGraph.edgeLabel(queryNode, assignedQueryNode);
                String actualEdgeLabel = dataNeighborEdgeLabels.get(assignedDataNode);
                if (actualEdgeLabel == null || !actualEdgeLabel.equals(expectedEdgeLabel)) {
                    return false;
                }
            }
            if (queryGraph.isDirected() && queryBackward) {
                DataNodeRecord assignedDataRecord = candidateAdjacency.get(assignedDataNode);
                if (assignedDataRecord == null) {
                    return false;
                }
                Map<String, String> assignedNeighborEdgeLabels =
                        edgeLabelCache.computeIfAbsent(assignedDataNode, k -> buildNeighborEdgeLabelMap(assignedDataRecord));
                String actualBackLabel = assignedNeighborEdgeLabels.get(dataRecord.getNodeId());
                String expectedBackLabel = queryGraph.edgeLabel(assignedQueryNode, queryNode);
                if (actualBackLabel == null || !actualBackLabel.equals(expectedBackLabel)) {
                    return false;
                }
            } else if (!queryGraph.isDirected() && queryBackward) {
                String expectedBackLabel = queryGraph.edgeLabel(assignedQueryNode, queryNode);
                String actualBackLabel = dataNeighborEdgeLabels.get(assignedDataNode);
                if (actualBackLabel == null || !actualBackLabel.equals(expectedBackLabel)) {
                    return false;
                }
            }
        }
        return true;
    }

    private Map<String, String> buildNeighborEdgeLabelMap(DataNodeRecord record) {
        Map<String, String> map = new HashMap<>();
        for (AdjacencyEntry e : record.getNeighbors()) {
            map.put(e.getNeighborId(), e.getEdgeLabel());
        }
        return map;
    }

    private String formatAssignment(Map<String, String> assignment) {
        List<String> keys = new ArrayList<>(assignment.keySet());
        Collections.sort(keys);
        List<String> pairs = new ArrayList<>();
        for (String key : keys) {
            pairs.add(key + "=" + assignment.get(key));
        }
        return String.join(",", pairs);
    }
}
