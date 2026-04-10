package edu.kent.cs730.graphmatch.model;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

public class QueryGraph {
    public static class Edge {
        private final String source;
        private final String target;
        private final String label;

        public Edge(String source, String target, String label) {
            this.source = source;
            this.target = target;
            this.label = label;
        }

        public String getSource() {
            return source;
        }

        public String getTarget() {
            return target;
        }

        public String getLabel() {
            return label;
        }
    }

    private boolean directed = false;
    private final Map<String, String> nodeLabels = new LinkedHashMap<>();
    private final Map<String, Map<String, String>> adjacency = new LinkedHashMap<>();
    private final List<Edge> edges = new ArrayList<>();

    public boolean isDirected() {
        return directed;
    }

    public Set<String> getNodeIds() {
        return nodeLabels.keySet();
    }

    public List<Edge> getEdges() {
        return edges;
    }

    public String getNodeLabel(String nodeId) {
        return nodeLabels.get(nodeId);
    }

    public int degree(String nodeId) {
        return adjacency.getOrDefault(nodeId, Collections.emptyMap()).size();
    }

    public Set<String> neighbors(String nodeId) {
        return adjacency.getOrDefault(nodeId, Collections.emptyMap()).keySet();
    }

    public boolean hasEdge(String src, String dst) {
        return adjacency.containsKey(src) && adjacency.get(src).containsKey(dst);
    }

    public String edgeLabel(String src, String dst) {
        return adjacency.getOrDefault(src, Collections.emptyMap()).get(dst);
    }

    public static QueryGraph load(Path path) throws IOException {
        QueryGraph graph = new QueryGraph();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                if (line.startsWith("directed=")) {
                    graph.directed = Boolean.parseBoolean(line.substring("directed=".length()).trim());
                    continue;
                }
                String[] parts = line.split("\\s+");
                if (parts.length < 3) {
                    throw new IllegalArgumentException("Invalid query line: " + line);
                }
                if (parts[0].equalsIgnoreCase("v")) {
                    graph.addNode(parts[1], parts[2]);
                } else if (parts[0].equalsIgnoreCase("e")) {
                    String edgeLabel = parts.length >= 4 ? parts[3] : "E";
                    graph.addEdge(parts[1], parts[2], edgeLabel);
                } else {
                    throw new IllegalArgumentException("Unknown query directive: " + parts[0]);
                }
            }
        }
        return graph;
    }

    public void addNode(String nodeId, String label) {
        nodeLabels.put(nodeId, label);
        adjacency.computeIfAbsent(nodeId, k -> new LinkedHashMap<>());
    }

    public void addEdge(String source, String target, String label) {
        if (!nodeLabels.containsKey(source) || !nodeLabels.containsKey(target)) {
            throw new IllegalArgumentException("Add nodes before edges: " + source + " -> " + target);
        }
        adjacency.computeIfAbsent(source, k -> new LinkedHashMap<>()).put(target, label);
        edges.add(new Edge(source, target, label));
        if (!directed) {
            adjacency.computeIfAbsent(target, k -> new LinkedHashMap<>()).put(source, label);
        }
    }

    public Map<String, SignatureRecord> computeSignatures(int maxK) {
    Map<String, SignatureRecord> result = new HashMap<>();
    for (String nodeId : getNodeIds()) {
        Map<String, Integer> hop1 = new TreeMap<>();
        for (String nbr : neighbors(nodeId)) {
            hop1.merge(getNodeLabel(nbr), 1, Integer::sum);
        }

        Map<String, Integer> hop2 = new TreeMap<>();
        if (maxK >= 2) {
            // within-2-hop ball, not exact 2-hop shell
            for (Map.Entry<String, Integer> e : hop1.entrySet()) {
                hop2.put(e.getKey(), e.getValue());
            }

            Set<String> seen = new HashSet<>();
            seen.add(nodeId);

            for (String mid : neighbors(nodeId)) {
                seen.add(mid);
            }

            Set<String> secondHopNodes = new LinkedHashSet<>();
            for (String mid : neighbors(nodeId)) {
                for (String candidate : neighbors(mid)) {
                    if (!candidate.equals(nodeId) && !neighbors(nodeId).contains(candidate)) {
                        secondHopNodes.add(candidate);
                    }
                }
            }

            for (String second : secondHopNodes) {
                hop2.merge(getNodeLabel(second), 1, Integer::sum);
            }
        }

        result.put(nodeId, new SignatureRecord(
                nodeId,
                getNodeLabel(nodeId),
                degree(nodeId),
                new HashSet<>(neighbors(nodeId)),
                hop1,
                hop2
            ));
    }
    return result;
    }

    public List<String> sortNodesForJoin(final Map<String, Set<String>> candidateSets) {
        List<String> nodes = new ArrayList<>(getNodeIds());
        nodes.sort(Comparator
                .comparingInt((String n) -> candidateSets.getOrDefault(n, Collections.emptySet()).size())
                .thenComparing((String n) -> -degree(n))
                .thenComparing(n -> nodeLabels.get(n))
                .thenComparing(n -> n));
        return nodes;
    }

    public String toFileFormat() {
        StringBuilder sb = new StringBuilder();
        sb.append("directed=").append(directed).append('\n');
        for (Map.Entry<String, String> entry : nodeLabels.entrySet()) {
            sb.append("v ").append(entry.getKey()).append(' ').append(entry.getValue()).append('\n');
        }
        Set<String> emitted = new HashSet<>();
        for (Edge e : edges) {
            String key = e.source + "->" + e.target + ":" + e.label;
            if (emitted.add(key)) {
                sb.append("e ").append(e.source).append(' ').append(e.target).append(' ').append(e.label).append('\n');
            }
        }
        return sb.toString();
    }
}
