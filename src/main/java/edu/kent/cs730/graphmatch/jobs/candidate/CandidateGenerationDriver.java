package edu.kent.cs730.graphmatch.jobs.candidate;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;

public class CandidateGenerationDriver {
    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            System.err.println("Usage: CandidateGenerationDriver <signature_input_dir> <query_file> <output_dir> <baseline|signature> <k>");
            System.exit(1);
        }

        Configuration conf = new Configuration();
        conf.setBoolean("graphmatch.use.signature", !"baseline".equalsIgnoreCase(args[3]));
        conf.setInt("graphmatch.k", Integer.parseInt(args[4]));

        Job job = Job.getInstance(conf, "NeighborSigMatch - Candidate Generation");
        job.setJarByClass(CandidateGenerationDriver.class);

        job.setMapperClass(CandidateGenerationMapper.class);
        job.setReducerClass(CandidateGenerationReducer.class);
        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(Text.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);

        job.addCacheFile(new Path(args[1]).toUri());
        FileInputFormat.addInputPath(job, new Path(args[0]));
        FileOutputFormat.setOutputPath(job, new Path(args[2]));

        System.exit(job.waitForCompletion(true) ? 0 : 2);
    }
}
