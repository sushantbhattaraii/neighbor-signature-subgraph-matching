package edu.kent.cs730.graphmatch.jobs.signature;

import edu.kent.cs730.graphmatch.model.AdjacencyEntry;
import edu.kent.cs730.graphmatch.model.DataNodeRecord;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.util.List;

public class SignatureConstructionMapper extends Mapper<LongWritable, Text, Text, Text> {
    private static final Text OUT_KEY = new Text();
    private static final Text OUT_VAL = new Text();

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString().trim();
        if (line.isEmpty()) {
            return;
        }
        DataNodeRecord record = DataNodeRecord.parseLine(line);
        String selfPayload = "S|" + record.getNodeLabel() + "|" + AdjacencyEntry.serializeList(record.getNeighbors());
        OUT_KEY.set(record.getNodeId());
        OUT_VAL.set(selfPayload);
        context.write(OUT_KEY, OUT_VAL);

        List<AdjacencyEntry> neighbors = record.getNeighbors();
        for (AdjacencyEntry requester : neighbors) {
            for (AdjacencyEntry candidate : neighbors) {
                OUT_KEY.set(requester.getNeighborId());
                OUT_VAL.set("T|" + candidate.getNeighborId() + "|" + candidate.getNeighborLabel());
                context.write(OUT_KEY, OUT_VAL);
            }
        }
    }
}
