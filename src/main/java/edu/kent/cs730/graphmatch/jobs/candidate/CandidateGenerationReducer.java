package edu.kent.cs730.graphmatch.jobs.candidate;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class CandidateGenerationReducer extends Reducer<Text, Text, Text, Text> {
    enum OutputCounters {
        CANDIDATE_PAIRS_EMITTED
    }

    private final Text outVal = new Text();

    @Override
    protected void reduce(Text key, Iterable<Text> values, Context context) throws IOException, InterruptedException {
        List<String> candidateIds = new ArrayList<>();
        for (Text value : values) {
            candidateIds.add(value.toString());
        }
        Collections.sort(candidateIds);
        context.getCounter(OutputCounters.CANDIDATE_PAIRS_EMITTED).increment(candidateIds.size());
        outVal.set(candidateIds.isEmpty() ? "-" : String.join(",", candidateIds));
        context.write(key, outVal);
    }
}
