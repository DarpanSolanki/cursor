import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import org.flywaydb.core.api.Location;
import org.flywaydb.core.internal.resource.filesystem.FileSystemResource;

/** Flyway 5.2.4 checksum — must match novopay-platform-initial-setup/flyway/lib/community. */
public class FlywayChecksum {
    public static void main(String[] args) {
        if (args.length != 1) {
            System.err.println("Usage: FlywayChecksum <absolute-or-relative-path-to-Vxxxx.sql>");
            System.exit(2);
        }
        Path file = Paths.get(args[0]).toAbsolutePath().normalize();
        Path dir = file.getParent();
        String filename = file.getFileName().toString();
        FileSystemResource resource = new FileSystemResource(
                new Location("filesystem:" + dir),
                filename,
                StandardCharsets.UTF_8);
        System.out.println(resource.checksum());
    }
}
