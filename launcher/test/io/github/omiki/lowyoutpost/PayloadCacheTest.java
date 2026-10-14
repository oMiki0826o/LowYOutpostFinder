package io.github.omiki.lowyoutpost;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

public final class PayloadCacheTest {
    public static void main(String[] args) throws Exception {
        byte[] value = "hello payload\n".getBytes(StandardCharsets.UTF_8);
        String digest = sha256(value);
        String valid = digest + "\t" + value.length + "\t0644\tapp/hello.txt\n";
        PayloadManifest manifest = PayloadManifest.parse(stream(valid));
        assert manifest.entries().size() == 1;
        assert manifest.totalBytes() == value.length;

        expectFailure("path", () -> PayloadManifest.parse(stream(
                digest + "\t1\t0644\t../escape")));
        expectFailure("path", () -> PayloadManifest.parse(stream(
                digest + "\t1\t0644\t/absolute")));
        expectFailure("path", () -> PayloadManifest.parse(stream(
                digest + "\t1\t0644\tapp\\escape")));
        expectFailure("Duplicate", () -> PayloadManifest.parse(stream(valid + valid)));
        expectFailure("mode", () -> PayloadManifest.parse(stream(
                digest + "\t1\tlink\tapp/link")));

        Path root = Files.createTempDirectory("lowy cache 中文 ");
        try {
            ClassLoader resources = new MemoryResources(Map.of("payload/app/hello.txt", value));
            Path first = PayloadCache.materialize(resources, manifest, root);
            assert Files.readString(first.resolve("app/hello.txt")).equals("hello payload\n");
            Path second = PayloadCache.materialize(resources, manifest, root);
            assert first.equals(second);

            Files.writeString(first.resolve(".complete"), "wrong");
            Path rebuilt = PayloadCache.materialize(resources, manifest, root);
            assert Files.readString(rebuilt.resolve(".complete")).equals(manifest.digest());

            CountDownLatch start = new CountDownLatch(1);
            AtomicReference<Path> left = new AtomicReference<>();
            AtomicReference<Path> right = new AtomicReference<>();
            Thread a = new Thread(() -> runMaterialize(resources, manifest, root, start, left));
            Thread b = new Thread(() -> runMaterialize(resources, manifest, root, start, right));
            a.start(); b.start(); start.countDown(); a.join(); b.join();
            assert left.get().equals(right.get());

            PayloadManifest badHash = PayloadManifest.parse(stream(
                    "0".repeat(64) + "\t" + value.length + "\t0644\tapp/hello.txt\n"));
            expectFailure("SHA-256", () -> PayloadCache.materialize(resources, badHash, root));
        } finally {
            deleteTree(root);
        }
        System.out.println("PayloadCacheTest: OK");
    }

    private static void runMaterialize(ClassLoader resources, PayloadManifest manifest,
                                       Path root, CountDownLatch start,
                                       AtomicReference<Path> output) {
        try {
            start.await();
            output.set(PayloadCache.materialize(resources, manifest, root));
        } catch (Exception error) {
            throw new RuntimeException(error);
        }
    }

    private static InputStream stream(String value) {
        return new ByteArrayInputStream(value.getBytes(StandardCharsets.UTF_8));
    }

    private static String sha256(byte[] value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
    }

    private static void expectFailure(String fragment, Throwing action) throws Exception {
        try {
            action.run();
            throw new AssertionError("Expected failure containing: " + fragment);
        } catch (IllegalArgumentException expected) {
            assert expected.getMessage().contains(fragment) : expected.getMessage();
        }
    }

    private static void deleteTree(Path root) throws Exception {
        try (var paths = Files.walk(root)) {
            for (Path path : paths.sorted(java.util.Comparator.reverseOrder()).toList()) {
                Files.deleteIfExists(path);
            }
        }
    }

    private interface Throwing { void run() throws Exception; }

    private static final class MemoryResources extends ClassLoader {
        private final Map<String, byte[]> values;
        MemoryResources(Map<String, byte[]> values) { this.values = values; }
        @Override public InputStream getResourceAsStream(String name) {
            byte[] value = values.get(name);
            return value == null ? null : new ByteArrayInputStream(value);
        }
    }
}
