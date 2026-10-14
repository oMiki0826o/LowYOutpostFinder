package io.github.omiki.lowyoutpost;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;

public record PayloadManifest(List<Entry> entries, long totalBytes, String digest) {
    private static final int MAX_ENTRIES = 50_000;
    private static final long MAX_BYTES = 2_000_000_000L;

    public record Entry(String sha256, long size, String mode, String path) {}

    public PayloadManifest {
        entries = List.copyOf(entries);
    }

    public static PayloadManifest parse(InputStream input) {
        if (input == null) throw new IllegalArgumentException("Missing payload manifest");
        List<Entry> entries = new ArrayList<>();
        Set<String> destinations = new HashSet<>();
        long total = 0;
        MessageDigest manifestDigest = digestInstance();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                byte[] canonical = (line + "\n").getBytes(StandardCharsets.UTF_8);
                manifestDigest.update(canonical);
                if (line.isBlank()) continue;
                String[] fields = line.split("\t", -1);
                if (fields.length != 4) throw new IllegalArgumentException("Malformed manifest record");
                String hash = fields[0];
                if (!hash.matches("[0-9a-f]{64}")) {
                    throw new IllegalArgumentException("Invalid SHA-256 in manifest");
                }
                long size;
                try { size = Long.parseLong(fields[1]); }
                catch (NumberFormatException error) { throw new IllegalArgumentException("Invalid payload size", error); }
                if (size < 0 || size > MAX_BYTES || total > MAX_BYTES - size) {
                    throw new IllegalArgumentException("Payload size exceeds limit");
                }
                String mode = fields[2];
                if (!(mode.equals("0644") || mode.equals("0755"))) {
                    throw new IllegalArgumentException("Invalid payload mode: " + mode);
                }
                String path = safePath(fields[3]);
                if (!destinations.add(path)) throw new IllegalArgumentException("Duplicate payload path: " + path);
                entries.add(new Entry(hash, size, mode, path));
                total += size;
                if (entries.size() > MAX_ENTRIES) throw new IllegalArgumentException("Too many payload entries");
            }
        } catch (IOException error) {
            throw new IllegalArgumentException("Unable to read payload manifest", error);
        }
        if (entries.isEmpty()) throw new IllegalArgumentException("Payload manifest is empty");
        return new PayloadManifest(entries, total,
                HexFormat.of().formatHex(manifestDigest.digest()));
    }

    private static String safePath(String value) {
        if (value.isBlank() || value.contains("\\") || value.indexOf('\0') >= 0) {
            throw new IllegalArgumentException("Unsafe payload path: " + value);
        }
        Path path = Path.of(value);
        if (path.isAbsolute()) throw new IllegalArgumentException("Unsafe payload path: " + value);
        Path normalized = path.normalize();
        if (normalized.startsWith("..") || !normalized.toString().replace('\\', '/').equals(value)) {
            throw new IllegalArgumentException("Unsafe payload path: " + value);
        }
        return value;
    }

    static MessageDigest digestInstance() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
}
