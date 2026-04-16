package edu.kent.cs730.graphmatch.jobs.verify;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;

public class SubgraphVerificationDriver {
    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            System.err.println("Usage: SubgraphVerificationDriver <adjacency_input_dir> <query_file> <candidate_file> <output_dir>");
            System.exit(1);
        }

        Configuration conf = new Configuration();

        // Increase timeout for long-running exact verification
        conf.setLong("mapreduce.task.timeout", 3600000L);           // 1 hour
        conf.setLong("mapreduce.task.stuck.timeout-ms", 3600000L); // 1 hour

        Job job = Job.getInstance(conf, "NeighborSigMatch - Subgraph Verification");
        
        job.setJarByClass(SubgraphVerificationDriver.class);

        job.setMapperClass(SubgraphVerificationMapper.class);
        job.setReducerClass(SubgraphVerificationReducer.class);
        job.setNumReduceTasks(1);

        job.setMapOutputKeyClass(IntWritable.class);
        job.setMapOutputValueClass(Text.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);

        job.addCacheFile(new Path(args[1]).toUri());
        job.addCacheFile(new Path(args[2]).toUri());

        FileInputFormat.addInputPath(job, new Path(args[0]));
        FileOutputFormat.setOutputPath(job, new Path(args[3]));

        System.exit(job.waitForCompletion(true) ? 0 : 2);
    }
}
