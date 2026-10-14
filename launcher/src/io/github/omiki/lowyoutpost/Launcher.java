package io.github.omiki.lowyoutpost;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class Launcher {
    private Launcher() {}

    public static String normalizeArchitecture(String value) {
        String normalized = value.toLowerCase(Locale.ROOT);
        return switch (normalized) {
            case "aarch64", "arm64" -> "arm64";
            case "amd64", "x86_64" -> "x86_64";
            default -> throw new IllegalArgumentException("Unsupported CPU architecture: " + value);
        };
    }

    public static void validatePlatform(String osName, String architecture, int javaFeature) {
        if (!osName.toLowerCase(Locale.ROOT).contains("mac")) {
            throw new IllegalArgumentException("This release supports macOS only");
        }
        if (javaFeature < 21) {
            throw new IllegalArgumentException("Java 21 or newer is required");
        }
        String expected = System.getProperty("lowy.targetArch", "arm64");
        String actual = normalizeArchitecture(architecture);
        if (!expected.equals(actual)) {
            throw new IllegalArgumentException(
                    "This JAR is for " + expected + ", but this Mac is " + actual);
        }
    }

    public static List<String> pythonCommand(Path payloadRoot) {
        List<String> command = new ArrayList<>();
        command.add(payloadRoot.resolve("runtime/bin/python3").toString());
        command.addAll(List.of("-I", "-s", "-E", "-m", "lowy_outpost_finder.gui"));
        return List.copyOf(command);
    }

    static ProcessBuilder processBuilder(Path payloadRoot, Path logFile) {
        ProcessBuilder builder = new ProcessBuilder(pythonCommand(payloadRoot));
        builder.directory(payloadRoot.resolve("app").toFile());
        var environment = builder.environment();
        environment.keySet().removeIf(Launcher::isSensitiveEnvironmentKey);
        environment.put("PYTHONPATH", payloadRoot.resolve("app").toString());
        environment.put("TCL_LIBRARY", payloadRoot.resolve("runtime/lib/tcl8.6").toString());
        environment.put("TK_LIBRARY", payloadRoot.resolve("runtime/lib/tk8.6").toString());
        builder.redirectErrorStream(true);
        builder.redirectOutput(ProcessBuilder.Redirect.appendTo(logFile.toFile()));
        return builder;
    }

    static boolean isSensitiveEnvironmentKey(String key) {
        String normalized = key.toLowerCase(Locale.ROOT);
        return normalized.contains("password") || normalized.contains("secret")
                || normalized.contains("token");
    }

    public static void main(String[] args) {
        ErrorReporter reporter = new ErrorReporter();
        try {
            validatePlatform(System.getProperty("os.name"), System.getProperty("os.arch"),
                    Runtime.version().feature());
            ClassLoader resources = Launcher.class.getClassLoader();
            PayloadManifest manifest = PayloadManifest.parse(
                    resources.getResourceAsStream("payload-manifest.tsv"));
            Path cacheRoot = Path.of(System.getProperty("user.home"), "Library", "Caches",
                    "LowYOutpostFinder", System.getProperty("lowy.appVersion", "unknown"));
            Path payload = PayloadCache.materialize(resources, manifest, cacheRoot);
            Process process = processBuilder(payload, reporter.logFile()).start();
            int exit = process.waitFor();
            if (exit != 0) throw new IllegalStateException("GUI exited with status " + exit);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            reporter.report("LowYOutpostFinder was interrupted", interrupted);
            System.exit(130);
        } catch (Exception error) {
            reporter.report("LowYOutpostFinder could not start", error);
            System.exit(1);
        }
    }
}
