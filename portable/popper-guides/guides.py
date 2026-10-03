"""Portable, reversible Popper integration for the online Curious Side Quests guides."""
from __future__ import annotations

import argparse
from contextlib import closing
import csv
import ctypes
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
SITE = 'https://curioussidequests.com/pinball/'
MODE = 'CSQ Tutorial'
TITLE = 'Cabinet Field Guide'
STATE_TABLE = 'CSQGuideInstaller'
MARK = 'rem CSQ-ONLINE-GUIDES-V1'
# Different editions must be chosen explicitly unless the filename is an exact known alias.
EXPLICIT = {'stranger-things-original-2020', 'beatles-007', 'beatles-stern-rules-edition',
            'cuphead-perdition', 'heavy-metal',
            'star-trek-2013', 'star-trek-next-generation', 'avengers', 'spider-man-classic'}


def catalog() -> dict:
    return json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))


def norm(value: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'\.(vpx|vpt)$', '',
                  re.split(r'[\\/]', value or '')[-1], flags=re.I)).strip().lower()


def words(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', norm(value)).strip()


def match_guide(row: dict, cat: dict) -> str:
    names = [row.get(k) or '' for k in ('GameFileName', 'GameName', 'GameDisplay')]
    exact = {cat['aliases'][norm(n)] for n in names if norm(n) in cat['aliases']}
    if exact:
        return next(iter(exact)) if len(exact) == 1 else ''
    candidates = set()
    for slug, title in cat['guides'].items():
        if slug in EXPLICIT:
            continue
        title_words = words(title)
        if len(title_words) < 6:
            continue
        if any((' ' + title_words + ' ') in (' ' + words(n) + ' ') for n in names):
            candidates.add(slug)
    return next(iter(candidates)) if len(candidates) == 1 else ''


def connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ValueError(f'Popper database not found: {path}')
    db = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    for table, needed in [('Games', {'GameID', 'EMUID', 'GameFileName', 'GameName',
                                    'GameDisplay', 'AltRunMode'}),
                          ('Emulators', {'EMUID', 'LaunchScript', 'PostScript'})]:
        columns = {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
        if not needed <= columns:
            db.close()
            raise ValueError(f'Unsupported Popper database: missing {table} columns.')
    return db


def get_state(db: sqlite3.Connection) -> dict | None:
    if not db.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',
                      (STATE_TABLE,)).fetchone():
        return None
    row = db.execute(f'SELECT data FROM {STATE_TABLE} WHERE id=1').fetchone()
    return json.loads(row[0]) if row else None


def make_plan(db: sqlite3.Connection, overrides: Path | None = None) -> list[dict]:
    cat = catalog()
    rows = [dict(r) for r in db.execute('SELECT * FROM Games ORDER BY GameName,GameID')]
    plan = []
    for row in rows:
        if not (row.get('GameFileName') or '').lower().endswith('.vpx'):
            continue
        plan.append({'GameID': row['GameID'], 'EMUID': row['EMUID'],
                     'GameName': row['GameName'], 'GameFileName': row['GameFileName'],
                     'Guide': match_guide(row, cat)})
    if overrides:
        by_id = {r['GameID']: r for r in plan}
        seen = set()
        with overrides.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                gid = int(row['GameID'])
                if gid in seen or gid not in by_id:
                    raise ValueError(f'Invalid or duplicate GameID in mapping CSV: {gid}')
                seen.add(gid)
                slug = row['Guide'].strip()
                if slug and slug not in cat['guides']:
                    raise ValueError(f'Unknown guide slug: {slug}')
                by_id[gid]['Guide'] = slug
    return plan


def write_preview(plan: list[dict]) -> Path:
    path = ROOT / 'table-mappings.csv'
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['GameID', 'EMUID', 'GameName',
                                              'GameFileName', 'Guide'])
        writer.writeheader()
        writer.writerows(plan)
    return path


def safe_batch_path(path: Path) -> str:
    value = str(path)
    if any(c in value for c in '%!\r\n"&^|<>'):
        raise ValueError('Extract the installer to a simple folder path without CMD special characters.')
    return value


def patch(original: str | None, command: str) -> str:
    text = original or ''
    if MARK in text or ':csq_online_guides' in text.lower():
        raise ValueError('An untracked CSQ integration already exists. No scripts were changed.')
    newline = '\r\n' if '\r\n' in text else '\n'
    branch = f'if /I "[ALTMODE]"=="{MODE}" goto csq_online_guides'
    # The original script remains intact after our branch, including @echo off.
    return branch + newline + text + newline + newline.join([
        MARK, 'goto :eof', ':csq_online_guides', command, 'exit /b', ''])


def idle() -> None:
    if os.name != 'nt':
        raise ValueError('Install/uninstall must run on Windows. Preview and tests are cross-platform.')
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], check=True,
                            capture_output=True, text=True)
    active = [r[0] for r in csv.reader(result.stdout.splitlines()) if r and
              re.match(r'(?i)^(PinUpMenu|PinUpPopper|PinUpMenuSetup|PinUpPackEditor|VPinball).*\.exe$', r[0])]
    if active:
        raise ValueError('Close Popper, Popper Setup, and VPX first: ' + ', '.join(active))


def backup(db: sqlite3.Connection, db_path: Path) -> Path:
    folder = db_path.parent / 'CSQ-Guide-Backups'
    folder.mkdir(exist_ok=True)
    target = folder / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-PUPDatabase.db')
    with closing(sqlite3.connect(target)) as copy:
        db.backup(copy)
    return target


def apply_install(db: sqlite3.Connection, plan: list[dict], settings: dict) -> None:
    """Install atomically; retain exact original scripts in a private database table."""
    if get_state(db):
        raise ValueError('Already installed. Uninstall before changing mappings or moving the folder.')
    selected = [r for r in plan if r['Guide']]
    if not selected:
        raise ValueError('No guides matched. Edit table-mappings.csv and use Install mappings.cmd.')
    for row in selected:
        safe_batch_path(Path(row['GameFileName']))
    base = safe_batch_path(ROOT)
    database = safe_batch_path(Path(settings['database']))
    python = f'{base}\\runtime\\pythonw.exe'
    script = f'{base}\\guides.py'
    launch = f'START "" "{python}" "{script}" launch --database "{database}" --table "[GAMEFULLNAME]"'
    close = f'"[STARTDIR]LAUNCH\\PUPCLOSER.EXE" WINTIT "{TITLE}" 5 0'
    state = {'version': 1, 'root': str(ROOT), 'settings': settings, 'emulators': [], 'games': []}
    db.execute('BEGIN IMMEDIATE')
    try:
        for emu_id in sorted({r['EMUID'] for r in selected}):
            row = db.execute('SELECT LaunchScript,PostScript FROM Emulators WHERE EMUID=?',
                             (emu_id,)).fetchone()
            if not row:
                raise ValueError(f'Missing emulator {emu_id}')
            entry = {'id': emu_id, 'before': list(row),
                     'after': [patch(row[0], launch), patch(row[1], close)]}
            db.execute('UPDATE Emulators SET LaunchScript=?,PostScript=? WHERE EMUID=?',
                       (*entry['after'], emu_id))
            state['emulators'].append(entry)
        for row in selected:
            old = db.execute('SELECT AltRunMode,GameFileName FROM Games WHERE GameID=? AND EMUID=?',
                             (row['GameID'], row['EMUID'])).fetchone()
            if not old or old[1] != row['GameFileName']:
                raise ValueError('Tables changed after preview. Run installer again.')
            if MODE.lower() in [s.strip().lower() for s in (old[0] or '').split(',')]:
                raise ValueError(f'{MODE} already exists on GameID {row["GameID"]}.')
            new = ((old[0] + ',') if old[0] else '') + MODE
            db.execute('UPDATE Games SET AltRunMode=? WHERE GameID=?', (new, row['GameID']))
            state['games'].append({**row, 'before': old[0], 'after': new})
        db.execute(f'CREATE TABLE IF NOT EXISTS {STATE_TABLE} (id INTEGER PRIMARY KEY,data TEXT NOT NULL)')
        db.execute(f'INSERT INTO {STATE_TABLE} VALUES (1,?)', (json.dumps(state),))
        db.commit()
    except Exception:
        db.rollback()
        raise


def apply_uninstall(db: sqlite3.Connection) -> None:
    state = get_state(db)
    if not state:
        raise ValueError('This installer has not modified this database.')
    db.execute('BEGIN IMMEDIATE')
    try:
        for entry in state['emulators']:
            row = db.execute('SELECT LaunchScript,PostScript FROM Emulators WHERE EMUID=?',
                             (entry['id'],)).fetchone()
            if not row or list(row) != entry['after']:
                raise ValueError('An emulator script changed since installation. Uninstall stopped '
                                 'without changes so your edits are preserved. See README recovery steps.')
        for entry in state['emulators']:
            db.execute('UPDATE Emulators SET LaunchScript=?,PostScript=? WHERE EMUID=?',
                       (*entry['before'], entry['id']))
        for game in state['games']:
            row = db.execute('SELECT AltRunMode,GameFileName,EMUID FROM Games WHERE GameID=?',
                             (game['GameID'],)).fetchone()
            if not row or row[1] != game['GameFileName'] or row[2] != game['EMUID']:
                continue  # Deleted/replaced rows are not ours to restore.
            new = game['before'] if row[0] == game['after'] else ','.join(
                v for v in (row[0] or '').split(',') if v.strip().lower() != MODE.lower())
            db.execute('UPDATE Games SET AltRunMode=? WHERE GameID=?', (new, game['GameID']))
        db.execute(f'DROP TABLE {STATE_TABLE}')
        db.commit()
    except Exception:
        db.rollback()
        raise


def find_database() -> Path:
    saved = ROOT / 'last-database.txt'
    candidates = [Path(saved.read_text().strip())] if saved.exists() else []
    candidates += [Path(f'{drive}:/{folder}/PUPDatabase.db') for drive in 'CDEFGHIJKLMNOPQRSTUVWXYZ'
                   for folder in ('vPinball/PinUPSystem', 'PinUPSystem')]
    found = list(dict.fromkeys(p.resolve() for p in candidates if p.is_file()))
    for i, path in enumerate(found, 1):
        print(f'  {i}. {path}')
    answer = input('Choose database number, or paste full PUPDatabase.db path: ').strip().strip('"')
    if answer.isdigit() and 1 <= int(answer) <= len(found):
        return found[int(answer) - 1]
    return Path(answer).resolve()


def edge_path() -> Path:
    for env in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
        path = Path(os.environ.get(env, '')) / 'Microsoft/Edge/Application/msedge.exe'
        if path.is_file():
            return path
    raise ValueError('Microsoft Edge was not found. Install Edge before using cabinet guides.')


def url_for(state: dict, table: str) -> str:
    hits = {r['Guide'] for r in state['games'] if norm(r['GameFileName']) == norm(table)}
    if len(hits) != 1:
        raise ValueError('This table has no unique guide mapping. Rerun setup to review its mapping.')
    settings = state['settings']
    return SITE + 'cabinet.html?' + urlencode({'page': hits.pop(),
                   'rot': settings['rotation'], 'zoom': settings['zoom']})


def launch(db_path: Path, table: str) -> None:
    with closing(connect(db_path)) as db:
        state = get_state(db)
        if not state:
            raise ValueError('Guide integration is not installed.')
        url = url_for(state, table)
    subprocess.Popen([str(edge_path()), '--kiosk', url, '--edge-kiosk-type=fullscreen',
                      '--no-first-run', '--user-data-dir=' +
                      str(Path(os.environ['LOCALAPPDATA']) / 'CSQPopperGuidesBrowser')],
                     close_fds=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preview', 'install', 'uninstall', 'launch'])
    parser.add_argument('--database', type=Path)
    parser.add_argument('--mappings', type=Path)
    parser.add_argument('--rotation', type=int, choices=[0, 90, 180, 270])
    parser.add_argument('--zoom', type=float)
    parser.add_argument('--table', default='')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    path = args.database.resolve() if args.database else find_database()
    if args.action == 'launch':
        launch(path, args.table)
        return
    with closing(connect(path)) as db:
        if args.action != 'uninstall':
            plan = make_plan(db, args.mappings)
            for r in plan:
                print(f'{r["GameID"]:5}  {r["GameName"]} -> {r["Guide"] or "(not selected)"}')
            # Detect duplicate basenames: launch receives a full path but Popper stores relative paths.
            names = {}
            for r in plan:
                if r['Guide']:
                    names.setdefault(norm(r['GameFileName']), set()).add(r['Guide'])
            if any(len(slugs) > 1 for slugs in names.values()):
                raise ValueError('Conflicting guide mappings for duplicate table filenames.')
            preview = write_preview(plan) if not args.mappings else args.mappings
            print(f'\n{sum(bool(r["Guide"]) for r in plan)} matched tables. Mapping CSV: {preview}')
            print('For corrections, edit the Guide column, then run Install mappings.cmd.')
        if args.action == 'preview':
            return
        idle()
        if args.action == 'install':
            edge_path()
            rotation = args.rotation
            if rotation is None:
                rotation = int(input('Screen rotation (0, 90, 180, 270) [270]: ') or '270')
            zoom = args.zoom if args.zoom is not None else float(input('Reading zoom (1 to 2) [1.35]: ') or '1.35')
            if rotation not in (0, 90, 180, 270) or not 1 <= zoom <= 2:
                raise ValueError('Invalid rotation or zoom.')
            if not (path.parent / 'Launch/PUPCloser.exe').is_file():
                raise ValueError('Popper Launch/PUPCloser.exe is missing; cannot safely provide the Exit action.')
            settings = {'database': str(path), 'rotation': rotation, 'zoom': zoom}
        if not args.yes and input(f'{args.action.title()} guide integration in {path}? Type YES: ') != 'YES':
            print('Cancelled. Popper was not changed.')
            return
        idle()
        print('Backup: ' + str(backup(db, path)))
        if args.action == 'install':
            apply_install(db, plan, settings)
            (ROOT / 'last-database.txt').write_text(str(path), encoding='utf-8')
        else:
            apply_uninstall(db)
        print('Done. Restart Popper.' if args.action == 'uninstall' else
              f'Done. Start Popper and choose {MODE} on a matched table. Keep this folder in place.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        message = str(error)
        if os.name == 'nt' and 'launch' in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, message, 'Curious Side Quests Guides', 0x10)
        else:
            print('ERROR: ' + message, file=sys.stderr)
        sys.exit(1)
