package edu.kent.cs730.graphmatch.jobs.verify;

import edu.kent.cs730.graphmatch.model.DataNodeRecord;
import edu.kent.cs730.graphmatch.util.CandidateFileUtils;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Paths;
import java.util.Map;
import java.util.Set;

public class SubgraphVerificationMapper extends Mapper<LongWritable, Text, IntWritable, Text> {
    private static final IntWritable GLOBAL_KEY = new IntWritable(1);
    private Set<String> candidateUniverse;

    @Override
    protected void setup(Context context) throws IOException {
        URI[] cacheFiles = context.getCacheFiles();
        if (cacheFiles == null || cacheFiles.length < 2) {
            throw new IOException("Query file and candidate file must be in Distributed Cache.");
        }
        Map<String, Set<String>> candidateSets = CandidateFileUtils.loadCandidateSets(Paths.get(cacheFiles[1].getPath()));
        candidateUniverse = CandidateFileUtils.union(candidateSets);
    }

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString().trim();
        if (line.isEmpty()) {
            return;
        }
        DataNodeRecord record = DataNodeRecord.parseLine(line);
        if (candidateUniverse.contains(record.getNodeId())) {
            context.write(GLOBAL_KEY, value);
        }
    }
}
