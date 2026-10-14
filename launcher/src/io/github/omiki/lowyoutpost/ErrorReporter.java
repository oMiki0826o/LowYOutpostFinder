package io.github.omiki.lowyoutpost;

import java.awt.GraphicsEnvironment;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import javax.swing.JOptionPane;

final class ErrorReporter {
    private static final long MAX_LOG_BYTES = 1_000_000;
    private final Path logFile;

    ErrorReporter() {
        this(Path.of(System.getProperty("user.home"), "Library", "Logs",
                "LowYOutpostFinder", "launcher.log"));
    }

    ErrorReporter(Path logFile) {
        this.logFile = logFile;
    }

    Path logFile() {
        return logFile;
    }

    void report(String title, Throwable error) {
        String detail = error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage();
        String message = title + ": " + detail + System.lineSeparator()
                + "Log: " + logFile;
        System.err.println(message);
        append(message);
        if (!GraphicsEnvironment.isHeadless()) {
            JOptionPane.showMessageDialog(null, message, title, JOptionPane.ERROR_MESSAGE);
        }
    }

    private void append(String message) {
        try {
            Files.createDirectories(logFile.getParent());
            if (Files.isRegularFile(logFile) && Files.size(logFile) > MAX_LOG_BYTES) {
                Files.move(logFile, logFile.resolveSibling("launcher.log.1"),
                        java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            }
            Files.writeString(logFile, Instant.now() + " " + message + System.lineSeparator(),
                    StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException ignored) {
            System.err.println("Unable to write launcher log: " + ignored.getMessage());
        }
    }
}
