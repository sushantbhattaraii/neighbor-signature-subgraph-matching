package edu.kent.cs730.graphmatch.util;

import java.util.Map;

public final class MultisetUtils {
    private MultisetUtils() {}

    public static boolean subsumes(Map<String, Integer> required, Map<String, Integer> available) {
        for (Map.Entry<String, Integer> entry : required.entrySet()) {
            int have = available.getOrDefault(entry.getKey(), 0);
            if (have < entry.getValue()) {
                return false;
            }
        }
        return true;
    }
}
