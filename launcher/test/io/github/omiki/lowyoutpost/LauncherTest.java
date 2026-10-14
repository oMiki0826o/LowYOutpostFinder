package io.github.omiki.lowyoutpost;

import java.nio.file.Path;
import java.util.List;

public final class LauncherTest {
    public static void main(String[] args) {
        assert "arm64".equals(Launcher.normalizeArchitecture("aarch64"));
        assert "arm64".equals(Launcher.normalizeArchitecture("arm64"));
        assert "x86_64".equals(Launcher.normalizeArchitecture("amd64"));
        assert "x86_64".equals(Launcher.normalizeArchitecture("x86_64"));
        expectFailure(() -> Launcher.normalizeArchitecture("ppc64"), "architecture");
        expectFailure(() -> Launcher.validatePlatform("Linux", "arm64", 21), "macOS");
        expectFailure(() -> Launcher.validatePlatform("Mac OS X", "arm64", 20), "Java 21");
        expectFailure(() -> Launcher.validatePlatform("Mac OS X", "x86_64", 21), "arm64");
        Launcher.validatePlatform("Mac OS X", "arm64", 21);

        Path payload = Path.of("/tmp/含 空白/payload");
        List<String> command = Launcher.pythonCommand(payload);
        assert command.equals(List.of(
                payload.resolve("runtime/bin/python3").toString(),
                "-I", "-s", "-E", "-m", "lowy_outpost_finder.gui")) : command;
        System.out.println("LauncherTest: OK");
    }

    private static void expectFailure(Runnable action, String fragment) {
        try {
            action.run();
            throw new AssertionError("Expected failure containing: " + fragment);
        } catch (IllegalArgumentException expected) {
            assert expected.getMessage().contains(fragment) : expected.getMessage();
        }
    }
}
