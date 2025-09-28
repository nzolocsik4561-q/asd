package java_demo;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public final class Main {
    private Main() {}

    public static String greeting(String name) {
        return "Hello, " + name + "!";
    }

    public static void main(String[] args) {
        var formatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME;
        var timestamp = LocalDateTime.now().format(formatter);
        System.out.println(greeting("Codex") + " @ " + timestamp);
    }
}
