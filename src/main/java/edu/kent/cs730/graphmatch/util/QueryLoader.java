package edu.kent.cs730.graphmatch.util;

import edu.kent.cs730.graphmatch.model.QueryGraph;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public final class QueryLoader {
    private QueryLoader() {}

    public static QueryGraph loadFromUri(URI uri) throws IOException {
        Path path = resolveLocalCachedPath(uri);
        return QueryGraph.load(path);
    }

    public static Path resolveLocalCachedPath(URI uri) throws IOException {
        Path direct = Paths.get(uri.getPath());
        if (Files.exists(direct)) {
            return direct;
        }
        String fileName = new File(uri.getPath()).getName();
        Path localized = Paths.get(fileName);
        if (Files.exists(localized)) {
            return localized;
        }
        throw new IOException("Could not resolve distributed cache file locally: " + uri);
    }
}
