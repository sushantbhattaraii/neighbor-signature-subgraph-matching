package edu.kent.cs730.graphmatch.model;

import java.util.ArrayList;
import java.util.List;

public class AdjacencyEntry {
    private final String neighborId;
    private final String neighborLabel;
    private final String edgeLabel;

    public AdjacencyEntry(String neighborId, String neighborLabel, String edgeLabel) {
        this.neighborId = neighborId;
        this.neighborLabel = neighborLabel;
        this.edgeLabel = edgeLabel;
    }

    public String getNeighborId() {
        return neighborId;
    }

    public String getNeighborLabel() {
        return neighborLabel;
    }

    public String getEdgeLabel() {
        return edgeLabel;
    }

    public String serialize() {
        return neighborId + ":" + neighborLabel + ":" + edgeLabel;
    }

    public static AdjacencyEntry parse(String token) {
        String[] parts = token.split(":", -1);
        if (parts.length < 2) {
            throw new IllegalArgumentException("Invalid adjacency token: " + token);
        }
        String edgeLabel = parts.length >= 3 ? parts[2] : "E";
        return new AdjacencyEntry(parts[0], parts[1], edgeLabel);
    }

    public static List<AdjacencyEntry> parseList(String raw) {
        List<AdjacencyEntry> result = new ArrayList<>();
        if (raw == null || raw.trim().isEmpty() || raw.equals("-")) {
            return result;
        }
        String[] tokens = raw.split(",");
        for (String token : tokens) {
            if (!token.trim().isEmpty()) {
                result.add(parse(token.trim()));
            }
        }
        return result;
    }

    public static String serializeList(List<AdjacencyEntry> entries) {
        if (entries == null || entries.isEmpty()) {
            return "-";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < entries.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(entries.get(i).serialize());
        }
        return sb.toString();
    }
}
