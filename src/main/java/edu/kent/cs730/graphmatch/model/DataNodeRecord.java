package edu.kent.cs730.graphmatch.model;

import java.util.List;

public class DataNodeRecord {
    private final String nodeId;
    private final String nodeLabel;
    private final List<AdjacencyEntry> neighbors;

    public DataNodeRecord(String nodeId, String nodeLabel, List<AdjacencyEntry> neighbors) {
        this.nodeId = nodeId;
        this.nodeLabel = nodeLabel;
        this.neighbors = neighbors;
    }

    public String getNodeId() {
        return nodeId;
    }

    public String getNodeLabel() {
        return nodeLabel;
    }

    public List<AdjacencyEntry> getNeighbors() {
        return neighbors;
    }

    public int getDegree() {
        return neighbors.size();
    }

    public String toLine() {
        return nodeId + "\t" + nodeLabel + "\t" + AdjacencyEntry.serializeList(neighbors);
    }

    public static DataNodeRecord parseLine(String line) {
        String[] parts = line.split("\t", -1);
        if (parts.length < 2) {
            throw new IllegalArgumentException("Invalid adjacency line: " + line);
        }
        String neighborsRaw = parts.length >= 3 ? parts[2] : "-";
        return new DataNodeRecord(parts[0], parts[1], AdjacencyEntry.parseList(neighborsRaw));
    }
}
