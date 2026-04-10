package edu.kent.cs730.graphmatch.jobs.candidate;

import edu.kent.cs730.graphmatch.model.QueryGraph;
import edu.kent.cs730.graphmatch.model.SignatureRecord;
import edu.kent.cs730.graphmatch.util.MultisetUtils;
import edu.kent.cs730.graphmatch.util.QueryLoader;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.net.URI;
import java.util.Map;

public class CandidateGenerationMapper extends Mapper<LongWritable, Text, Text, Text> {
    enum CandidateCounters {
        TOTAL_NODE_QUERY_PAIRS,
        LABEL_AND_DEGREE_PASSED,
        SIGNATURE_PASSED
    }

    private final Text outKey = new Text();
    private final Text outVal = new Text();
    private QueryGraph queryGraph;
    private Map<String, SignatureRecord> querySignatures;
    private boolean useSignature;
    private int maxHop;

    @Override
    protected void setup(Context context) throws IOException {
        URI[] cacheFiles = context.getCacheFiles();
        if (cacheFiles == null || cacheFiles.length == 0) {
            throw new IOException("Query graph file must be provided via Distributed Cache.");
        }
        queryGraph = QueryLoader.loadFromUri(cacheFiles[0]);
        maxHop = context.getConfiguration().getInt("graphmatch.k", 2);
        useSignature = context.getConfiguration().getBoolean("graphmatch.use.signature", true);
        querySignatures = queryGraph.computeSignatures(maxHop);
    }

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString().trim();
        if (line.isEmpty()) {
            return;
        }
        SignatureRecord dataSig = SignatureRecord.parseLine(line.substring(line.indexOf('\t') + 1));
        for (String queryNodeId : queryGraph.getNodeIds()) {
            context.getCounter(CandidateCounters.TOTAL_NODE_QUERY_PAIRS).increment(1);
            SignatureRecord querySig = querySignatures.get(queryNodeId);
            if (!querySig.getNodeLabel().equals(dataSig.getNodeLabel())) {
                continue;
            }
            if (dataSig.getDegree() < querySig.getDegree()) {
                continue;
            }
            context.getCounter(CandidateCounters.LABEL_AND_DEGREE_PASSED).increment(1);
            boolean ok = true;
            if (useSignature) {
                ok = MultisetUtils.subsumes(querySig.getHop1(), dataSig.getHop1());
                if (ok && maxHop >= 2) {
                    ok = MultisetUtils.subsumes(querySig.getHop2(), dataSig.getHop2());
                }
            }
            if (!ok) {
                continue;
            }
            context.getCounter(CandidateCounters.SIGNATURE_PASSED).increment(1);
            outKey.set(queryNodeId);
            outVal.set(dataSig.getNodeId());
            context.write(outKey, outVal);
        }
    }
}
