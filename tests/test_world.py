import json
from pathlib import Path
import tempfile
import unittest

from megalodonte_cli.world import CompilationWorld, java_tokens


class CompilationWorldTests(unittest.TestCase):
    def test_full_snapshot_then_tokenized_delta_resources_and_environment_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'app'
            session = root / 'session'
            java = project / 'src/main/java/demo/App.java'
            resource = project / 'src/main/resources/title.txt'
            java.parent.mkdir(parents=True)
            resource.parent.mkdir(parents=True)
            java.write_text('package demo; import java.util.List; class App { int value = 1; }')
            resource.write_text('one')
            (project / '.env').write_text('SECRET=first')
            world = CompilationWorld(project, session)

            first = world.update()
            self.assertEqual('PROJECT_SNAPSHOT', first['type'])
            self.assertFalse(first['requiresRestart'])
            mapped = {item['path']: item for item in first['entries']}
            self.assertEqual(['App'], list(mapped['src/main/java/demo/App.java']['declared_types']))
            self.assertEqual(['java.util.List'], list(mapped['src/main/java/demo/App.java']['imports']))
            self.assertFalse((world.inputs / '.env').exists())
            self.assertNotIn('SECRET=first', json.dumps(first))

            java.write_text('package demo; import java.util.List; class App { int value = 2; }')
            resource.write_text('two')
            second = world.update()
            self.assertEqual('PROJECT_DELTA', second['type'])
            self.assertFalse(second['requiresRestart'])
            self.assertEqual({'src/main/java/demo/App.java', 'src/main/resources/title.txt'},
                             {item['path'] for item in second['delta']['changed']})
            self.assertEqual('two', (world.inputs / 'src/main/resources/title.txt').read_text())
            output = root / 'classes'
            compiled = output / 'demo/App.class'
            compiled.parent.mkdir(parents=True)
            compiled.write_bytes(b'first class')
            result = world.response(second, 'APPLIED', [output])
            self.assertEqual(['demo/App.class'],
                             [item['path'] for item in result['artifactDelta']['changed']])
            fourth = world.update()
            unchanged = world.response(fourth, 'APPLIED', [output])
            self.assertEqual([], unchanged['artifactDelta']['changed'])

            (project / '.env').write_text('SECRET=second')
            third = world.update()
            self.assertTrue(third['requiresRestart'])
            self.assertEqual(['environment'], third['restartReasons'])
            self.assertNotIn('SECRET=second', (world.protocol / 'latest-request.json').read_text())

    def test_comments_do_not_change_java_token_hash(self):
        self.assertEqual(java_tokens('class A { int x; }'), java_tokens('// note\nclass A { /* x */ int x; }'))


if __name__ == '__main__':
    unittest.main()
