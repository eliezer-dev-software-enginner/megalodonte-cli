"""Final-stage integration: real host windows survive structural Java edits.

Requires display, JDK 25 and published libraries. Uses only a disposable app.
Run: PYTHONPATH=src python tests/integration_native_host.py
"""
from pathlib import Path
import tempfile

from megalodonte_cli.cli import create
from megalodonte_cli.dev import fingerprint
from megalodonte_cli.native_dev import NativeDevelopmentSession

WORKER = '''package host_demo;
import megalodonte.application.messaging.*;
import static megalodonte.application.messaging.NativeUi.*;
import java.util.List;
public class WorkerMain {
    static void main() throws Exception {
        NativeWorker.run(new NativeWorker.Application() {
            // STRUCTURE
            public Snapshot prepare(State state) { return screen(); }
            public Snapshot onEvent(Event event) { return screen(); }
            Snapshot screen() {
                return new Snapshot(List.of(
                    new Window("one", "One", 300, 150, column("root", text("version", "v1"))),
                    new Window("two", "Two", 300, 150, column("root", button("save", "Save")))));
            }
        });
    }
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='native-host-consumer-') as directory:
        root = Path(directory)
        app = create('host-demo', 'native', 'Native host integration', root)
        source = app / 'src/main/java/host_demo/WorkerMain.java'
        source.write_text(WORKER)
        session_dir = root / 'session'
        session_dir.mkdir()
        session = NativeDevelopmentSession(app, session_dir, True, 'host_demo.WorkerMain')
        try:
            assert session.build(fingerprint(session.watch))
            pid = session.process.pid
            first = session.last_result
            extra = source.with_name('Extra.java')
            extra.write_text('package host_demo; class Extra { static String value() { return "v2"; } }')
            source.write_text(WORKER.replace('// STRUCTURE', 'int newField;').replace('"v1"', 'Extra.value()'))
            assert session.build(fingerprint(session.watch)), 'Added classes/fields must replace worker'
            second = session.last_result
            assert second['workerPid'] != first['workerPid']
            assert second['identities'] == first['identities'], 'Native Stage/Scene identities must survive'
            assert session.process.pid == pid and session.process.poll() is None
            source.write_text('invalid Java')
            assert not session.build(fingerprint(session.watch))
            assert session.process.poll() is None
            # A compiling but invalid candidate must not close the old windows.
            source.write_text(WORKER.replace('"two", "Two"', '"one", "Duplicate"'))
            assert not session.build(fingerprint(session.watch))
            assert session.last_result['status'] == 'REJECTED'
            # Class removal is also a structural change and must retain the host.
            source.write_text(WORKER)
            extra.unlink()
            assert session.build(fingerprint(session.watch))
            assert session.last_result['identities'] == first['identities']
            assert session.process.pid == pid
            print('PASS: added/removed classes, added field, new worker PID, same host/Stage/Scene, compilation failure and candidate rejection')
        finally:
            session.stop()
        assert session.process.poll() is not None


if __name__ == '__main__':
    main()
