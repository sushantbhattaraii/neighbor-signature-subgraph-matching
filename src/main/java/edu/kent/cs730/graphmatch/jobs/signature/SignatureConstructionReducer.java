package edu.kent.cs730.graphmatch.jobs.signature;

import edu.kent.cs730.graphmatch.model.AdjacencyEntry;
import edu.kent.cs730.graphmatch.model.SignatureRecord;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class SignatureConstructionReducer extends Reducer<Text, Text, Text, Text> {
    private static final Text OUT_VAL = new Text();

    @Override
    protected void reduce(Text key, Iterable<Text> values, Context context) throws IOException, InterruptedException {
        String nodeId = key.toString();
        String nodeLabel = null;
        List<AdjacencyEntry> neighbors = null;
        Set<String> neighborIds = new HashSet<>();
        Map<String, Integer> hop1 = new HashMap<>();
        Map<String, String> secondHopUnique = new LinkedHashMap<>();

        for (Text t : values) {
            String[] parts = t.toString().split("\\|", -1);
            if (parts[0].equals("S")) {
                nodeLabel = parts[1];
                neighbors = AdjacencyEntry.parseList(parts.length >= 3 ? parts[2] : "-");
                for (AdjacencyEntry e : neighbors) {
                    neighborIds.add(e.getNeighborId());
                    hop1.merge(e.getNeighborLabel(), 1, Integer::sum);
                }
            } else if (parts[0].equals("T")) {
                if (parts.length >= 3) {
                    secondHopUnique.put(parts[1], parts[2]);
                }
            }
        }

        if (nodeLabel == null || neighbors == null) {
            return;
        }

        Map<String, Integer> hop2 = new HashMap<>();

        // hop2 = within-2-hop ball, so start with hop1 counts
        for (Map.Entry<String, Integer> e : hop1.entrySet()) {
            hop2.merge(e.getKey(), e.getValue(), Integer::sum);
        }

        // then add exact 2-hop nodes that are not already direct neighbors
        for (Map.Entry<String, String> entry : secondHopUnique.entrySet()) {
            String candidateId = entry.getKey();
            if (candidateId.equals(nodeId) || neighborIds.contains(candidateId)) {
                continue;
            }
            hop2.merge(entry.getValue(), 1, Integer::sum);
        }

        SignatureRecord record = new SignatureRecord(nodeId, nodeLabel, neighbors.size(), neighborIds, hop1, hop2);
        OUT_VAL.set(record.toLine());
        context.write(key, OUT_VAL);
    }
}
