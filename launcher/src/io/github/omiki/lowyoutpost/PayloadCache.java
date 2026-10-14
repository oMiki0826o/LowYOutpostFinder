package io.github.omiki.lowyoutpost;

import java.io.IOException;
import java.io.InputStream;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermission;
import java.security.DigestInputStream;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.Set;
import java.util.UUID;

public final class PayloadCache {
    private PayloadCache() {}

    public static Path materialize(ClassLoader resources, PayloadManifest manifest,
                                   Path cacheRoot) {
        String id = "payload-" + manifest.digest();
        Object localLock = (cacheRoot.toAbsolutePath().normalize() + ":" + id).intern();
        synchronized (localLock) {
            try {
                Files.createDirectories(cacheRoot);
                Path lockPath = cacheRoot.resolve(id + ".lock");
                try (FileChannel channel = FileChannel.open(lockPath, StandardOpenOption.CREATE,
                        StandardOpenOption.WRITE); FileLock ignored = channel.lock()) {
                    return materializeLocked(resources, manifest, cacheRoot, id);
                }
            } catch (IOException error) {
                throw new IllegalArgumentException("Unable to create payload cache", error);
            }
        }
    }

    private static Path materializeLocked(ClassLoader resources, PayloadManifest manifest,
                                          Path cacheRoot, String id) throws IOException {
        Path destination = cacheRoot.resolve(id);
        Path marker = destination.resolve(".complete");
        if (Files.isRegularFile(marker)
                && Files.readString(marker).equals(manifest.digest())) return destination;
        deleteTree(destination);
        Path temporary = cacheRoot.resolve(id + ".tmp-" + UUID.randomUUID());
        try {
            Files.createDirectories(temporary);
            for (PayloadManifest.Entry entry : manifest.entries()) {
                Path output = temporary.resolve(entry.path()).normalize();
                if (!output.startsWith(temporary)) throw new IllegalArgumentException("Unsafe payload path");
                Files.createDirectories(output.getParent());
                try (InputStream raw = resources.getResourceAsStream("payload/" + entry.path())) {
                    if (raw == null) throw new IllegalArgumentException("Missing payload resource: " + entry.path());
                    var digest = PayloadManifest.digestInstance();
                    long copied;
                    try (DigestInputStream input = new DigestInputStream(raw, digest)) {
                        copied = Files.copy(input, output);
                    }
                    if (copied != entry.size()) throw new IllegalArgumentException("Payload size mismatch: " + entry.path());
                    String actual = HexFormat.of().formatHex(digest.digest());
                    if (!actual.equals(entry.sha256())) throw new IllegalArgumentException("Payload SHA-256 mismatch: " + entry.path());
                }
                setMode(output, entry.mode());
            }
            Files.writeString(temporary.resolve(".complete"), manifest.digest(),
                    StandardOpenOption.CREATE_NEW);
            try {
                Files.move(temporary, destination, StandardCopyOption.ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException unsupported) {
                Files.move(temporary, destination);
            }
            return destination;
        } finally {
            deleteTree(temporary);
        }
    }

    private static void setMode(Path path, String mode) throws IOException {
        try {
            Set<PosixFilePermission> permissions = mode.equals("0755")
                    ? Set.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE,
                             PosixFilePermission.OWNER_EXECUTE, PosixFilePermission.GROUP_READ,
                             PosixFilePermission.GROUP_EXECUTE, PosixFilePermission.OTHERS_READ,
                             PosixFilePermission.OTHERS_EXECUTE)
                    : Set.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE,
                             PosixFilePermission.GROUP_READ, PosixFilePermission.OTHERS_READ);
            Files.setPosixFilePermissions(path, permissions);
        } catch (UnsupportedOperationException ignored) {
            if (mode.equals("0755") && !path.toFile().setExecutable(true, false)) {
                throw new IOException("Unable to mark payload executable: " + path);
            }
        }
    }

    private static void deleteTree(Path root) throws IOException {
        if (!Files.exists(root)) return;
        try (var paths = Files.walk(root)) {
            for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) {
                Files.deleteIfExists(path);
            }
        }
    }
}
