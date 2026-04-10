package edu.kent.cs730.graphmatch.util;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

public final class CandidateFileUtils {
    private CandidateFileUtils() {}

    public static Map<String, Set<String>> loadCandidateSets(Path path) throws IOException {
        Map<String, Set<String>> result = new HashMap<>();
        Path resolved = resolveLocalPath(path);
        try (BufferedReader reader = Files.newBufferedReader(resolved, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.trim().isEmpty()) {
                    continue;
                }
                String[] parts = line.split("\t", -1);
                if (parts.length < 2) {
                    continue;
                }
                if (parts[1].trim().isEmpty() || parts[1].equals("-")) {
                    result.put(parts[0], new LinkedHashSet<>());
                } else {
                    result.put(parts[0], new LinkedHashSet<>(Arrays.asList(parts[1].split(","))));
                }
            }
        }
        return result;
    }

    private static Path resolveLocalPath(Path path) throws IOException {
        if (Files.exists(path)) {
            return path;
        }
        Path localized = Paths.get(path.getFileName().toString());
        if (Files.exists(localized)) {
            return localized;
        }
        throw new IOException("Could not resolve distributed cache file locally: " + path);
    }

    public static Set<String> union(Map<String, Set<String>> candidateSets) {
        Set<String> union = new HashSet<>();
        for (Set<String> values : candidateSets.values()) {
            union.addAll(values);
        }
        return union;
    }

    public static Set<String> emptyIfMissing(Map<String, Set<String>> map, String key) {
        return map.getOrDefault(key, Collections.emptySet());
    }
}
