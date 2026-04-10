package edu.kent.cs730.graphmatch.model;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

public class SignatureRecord {
    private final String nodeId;
    private final String nodeLabel;
    private final int degree;
    private final Set<String> neighborIds;
    private final Map<String, Integer> hop1;
    private final Map<String, Integer> hop2;

    public SignatureRecord(String nodeId,
                           String nodeLabel,
                           int degree,
                           Set<String> neighborIds,
                           Map<String, Integer> hop1,
                           Map<String, Integer> hop2) {
        this.nodeId = nodeId;
        this.nodeLabel = nodeLabel;
        this.degree = degree;
        this.neighborIds = neighborIds;
        this.hop1 = hop1;
        this.hop2 = hop2;
    }

    public String getNodeId() {
        return nodeId;
    }

    public String getNodeLabel() {
        return nodeLabel;
    }

    public int getDegree() {
        return degree;
    }

    public Set<String> getNeighborIds() {
        return neighborIds;
    }

    public Map<String, Integer> getHop1() {
        return hop1;
    }

    public Map<String, Integer> getHop2() {
        return hop2;
    }

    public String toLine() {
        return nodeId + "\t"
                + nodeLabel + "\t"
                + degree + "\t"
                + serializeSet(neighborIds) + "\t"
                + serializeMultiset(hop1) + "\t"
                + serializeMultiset(hop2);
    }

    public static SignatureRecord parseLine(String line) {
        String[] parts = line.split("\t", -1);
        if (parts.length < 6) {
            throw new IllegalArgumentException("Invalid signature line: " + line);
        }
        return new SignatureRecord(
                parts[0],
                parts[1],
                Integer.parseInt(parts[2]),
                parseSet(parts[3]),
                parseMultiset(parts[4]),
                parseMultiset(parts[5])
        );
    }

    public static String serializeMultiset(Map<String, Integer> multiset) {
        if (multiset == null || multiset.isEmpty()) {
            return "-";
        }
        Map<String, Integer> sorted = new TreeMap<>(multiset);
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (Map.Entry<String, Integer> entry : sorted.entrySet()) {
            if (!first) {
                sb.append('|');
            }
            first = false;
            sb.append(entry.getKey()).append('=').append(entry.getValue());
        }
        return sb.toString();
    }

    public static Map<String, Integer> parseMultiset(String raw) {
        if (raw == null || raw.trim().isEmpty() || raw.equals("-")) {
            return new LinkedHashMap<>();
        }
        Map<String, Integer> map = new HashMap<>();
        for (String token : raw.split("\\|")) {
            if (token.trim().isEmpty()) {
                continue;
            }
            String[] parts = token.split("=", -1);
            map.put(parts[0], Integer.parseInt(parts[1]));
        }
        return map;
    }

    public static String serializeSet(Set<String> values) {
        if (values == null || values.isEmpty()) {
            return "-";
        }
        String[] arr = values.toArray(new String[0]);
        Arrays.sort(arr);
        return String.join(",", arr);
    }

    public static Set<String> parseSet(String raw) {
        if (raw == null || raw.trim().isEmpty() || raw.equals("-")) {
            return new HashSet<>();
        }
        return new HashSet<>(Arrays.asList(raw.split(",")));
    }

    public static Map<String, Integer> emptyMultiset() {
        return Collections.emptyMap();
    }
}
