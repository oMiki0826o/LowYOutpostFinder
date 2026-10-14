package io.github.omiki.lowyoutpost;

public final class ErrorReporterTest {
    public static void main(String[] args) {
        var error = new IllegalArgumentException("outer", new java.io.IOException("inner cause"));
        String detail = ErrorReporter.describe(error);
        assert detail.contains("outer") : detail;
        assert detail.contains("inner cause") : detail;
        System.out.println("ErrorReporterTest: OK");
    }
}
