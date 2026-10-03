"""Exercise real SQLite changes, rollback and routing without touching a live cabinet."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / 'portable/popper-guides/guides.py'
spec = importlib.util.spec_from_file_location('portable_guides', MODULE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'PUPDatabase.db'
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE Emulators(EMUID INTEGER PRIMARY KEY,LaunchScript TEXT,PostScript TEXT);
        CREATE TABLE Games(GameID INTEGER PRIMARY KEY, EMUID INTEGER,GameFileName TEXT,
          GameName TEXT,GameDisplay TEXT,AltRunMode TEXT);
        INSERT INTO Emulators VALUES(7,'@echo off\r\nSTART original.exe','close original');
        INSERT INTO Emulators VALUES(42,'other emulator',NULL);
        INSERT INTO Games VALUES(1,7,'Scared Stiff (Bally 1996) VPW 1.5.vpx','Scared Stiff','',NULL);
        INSERT INTO Games VALUES(2,7,'Unrecognized.vpx','Unrecognized','','vr');
        INSERT INTO Games VALUES(3,42,'Fish Tales.vpx','Fish Tales','','vr');
        INSERT INTO Games VALUES(4,42,'FX3.exe','Scared Stiff','','');
        ''')
        self.before = self.snapshot()
        self.settings = {'database': str(self.path), 'rotation': 90, 'zoom': 1.35}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def snapshot(self):
        return {t: [tuple(r) for r in self.db.execute(f'SELECT * FROM {t}')]
                for t in ['Emulators', 'Games']}

    def install(self):
        g.apply_install(self.db, g.make_plan(self.db), self.settings)

    def test_match_and_exact_roundtrip_including_nulls(self):
        plan = g.make_plan(self.db)
        self.assertEqual([r['Guide'] for r in plan if r['GameID'] == 1], ['scared-stiff'])
        self.assertNotIn(4, [r['GameID'] for r in plan])
        self.install()
        self.assertEqual(self.db.execute('SELECT AltRunMode FROM Games WHERE GameID=2').fetchone()[0], 'vr')
        self.assertEqual(self.db.execute('SELECT AltRunMode FROM Games WHERE GameID=3').fetchone()[0], 'vr,CSQ Tutorial')
        g.apply_uninstall(self.db)
        self.assertEqual(self.snapshot(), self.before)
        self.assertIsNone(g.get_state(self.db))

    def test_double_install_does_not_duplicate(self):
        self.install()
        after = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Already installed'):
            self.install()
        self.assertEqual(self.snapshot(), after)

    def test_changed_script_aborts_whole_uninstall(self):
        self.install()
        self.db.execute("UPDATE Emulators SET PostScript=PostScript || ' user edit' WHERE EMUID=42")
        self.db.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'changed since'):
            g.apply_uninstall(self.db)
        self.assertEqual(self.snapshot(), before)
        self.assertIsNotNone(g.get_state(self.db))

    def test_late_install_failure_rolls_back_every_emulator(self):
        self.db.execute('UPDATE Games SET AltRunMode=? WHERE GameID=3', (g.MODE,))
        self.db.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.install()
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(g.get_state(self.db))

    def test_uninstall_preserves_new_alternate_mode(self):
        self.install()
        self.db.execute("UPDATE Games SET AltRunMode=AltRunMode || ',desktop' WHERE GameID=3")
        self.db.commit()
        g.apply_uninstall(self.db)
        self.assertEqual(self.db.execute('SELECT AltRunMode FROM Games WHERE GameID=3').fetchone()[0], 'vr,desktop')

    def test_streamed_url_has_no_local_filename(self):
        self.install()
        url = g.url_for(g.get_state(self.db), r'E:\Other\Scared Stiff (Bally 1996) VPW 1.5.vpx')
        self.assertEqual(url, 'https://curioussidequests.com/pinball/cabinet.html?page=scared-stiff&rot=90&zoom=1.35')
        with self.assertRaises(ValueError):
            g.url_for(g.get_state(self.db), 'missing.vpx')

    def test_backup_is_complete_and_readable(self):
        backup = g.backup(self.db, self.path)
        with closing(sqlite3.connect(backup)) as saved:
            self.assertEqual(saved.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(saved.execute('SELECT count(*) FROM Games').fetchone()[0], 4)

    def test_ambiguous_and_edition_matches_are_not_guessed(self):
        cat = g.catalog()
        self.assertEqual(g.match_guide({'GameName': 'Star Trek unknown version'}, cat), '')
        self.assertEqual(g.match_guide({'GameName': 'Stranger Things newer edition'}, cat), '')
        self.assertEqual(g.match_guide({'GameName': 'Scared Stiff Fish Tales'}, cat), '')

    def test_csv_override_and_blank_opt_out(self):
        path = Path(self.temp.name) / 'map.csv'
        path.write_text('GameID,Guide\n1,\n2,scared-stiff\n')
        rows = {r['GameID']: r for r in g.make_plan(self.db, path)}
        self.assertEqual(rows[1]['Guide'], '')
        self.assertEqual(rows[2]['Guide'], 'scared-stiff')
        path.write_text('GameID,Guide\n2,../../bad\n')
        with self.assertRaises(ValueError):
            g.make_plan(self.db, path)

    def test_batch_paths_reject_expansion_and_injection(self):
        for value in ['C:/percent%TEMP%', 'C:/bang!dir', 'C:/a&b', 'C:/bad\npath']:
            with self.assertRaises(ValueError):
                g.safe_batch_path(Path(value))


if __name__ == '__main__':
    unittest.main()
