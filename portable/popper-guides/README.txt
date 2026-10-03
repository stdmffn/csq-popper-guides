CURIOUS SIDE QUESTS -- ONLINE PINBALL GUIDES FOR PINUP POPPER
Version 1.0 -- Windows 10/11 x64, PinUP Popper, Microsoft Edge

INSTALL
1. Extract the entire ZIP into a permanent folder, for example
   C:\PinballGuides. Do not run it from inside the ZIP or a temporary folder.
2. Close Popper, Popper Setup, and Visual Pinball.
3. Double-click Install.cmd. Select the PUPDatabase.db belonging to your
   cabinet. Common C: through Z: install locations are detected; you can
   also paste a full path. Administrator privileges are not normally needed.
4. Review the table-to-guide list. Unrecognized/ambiguous tables are skipped.
   Choose the screen rotation and reading zoom, then type YES to install.
5. Start Popper. On a matched table, select its alternate launch option
   "CSQ Tutorial". Normal play and existing alternate modes remain available.

The installer backs up your database beside it in CSQ-Guide-Backups before
changing it. It only adds an alternate mode and a branch to the associated
emulator's launch/exit scripts. It does not replace your database with
someone else's, change table files, or download site artwork.

KEEP THIS EXTRACTED FOLDER IN PLACE after installation. Popper refers to its
small launcher and bundled Python runtime. You do not need Python installed.
To move the folder, uninstall first, move it, and reinstall.

ONLINE CONTENT
Guides stream from https://curioussidequests.com/pinball/ and require an
internet connection. Website updates appear without reinstalling. Edge may
cache media normally; this is not an offline guide package. Only the guide
slug, rotation and zoom are sent in the URL, not your local table filenames
or Popper database. A separate Edge profile keeps your ordinary browsing
session separate from the cabinet guide window.

TABLE MAPPINGS
Preview.cmd writes table-mappings.csv without modifying Popper. You can
also cancel Install.cmd at the YES prompt after inspecting its preview.
For a different filename/edition, edit the CSV's Guide column in a text
editor, using the slugs in catalog.json. Leave it blank to omit a table.
Then run Install mappings.cmd. Do not edit GameID or GameFileName.
Only .vpx entries are eligible; multiple VPX emulator IDs are supported.
The preview uses exact known aliases and conservative title matches.
Check editions yourself; similarly named games can have different rules.
If you add tables later, uninstall and reinstall to refresh the mappings.

CONTROLS AND DISPLAY
Right flipper / Right Shift: scroll down.
Left flipper / Left Shift: scroll up.
Right/left MagnaSave / Ctrl: next/previous section.
Start / Enter / 1: open shot map (where available).
Both Ctrl/MagnaSave together: rotate a quarter turn.
Plus/minus: adjust reading zoom for the current session.
Your Popper Exit button closes the guide through Popper's PUPCloser utility.
Default display is rotated 270 degrees, zoom 1.35. Choose 0 for a Windows
screen already oriented upright. Standard keyboard mappings and common
VPX gamepad buttons are supported; unusual controller mappings may differ.
The guide opens on Edge's chosen display; multi-monitor placement must be
checked on your cabinet. This first version does not force a monitor number.

UNINSTALL AND RECOVERY
Close Popper and VPX, then double-click Uninstall.cmd and choose the same DB.
Uninstall restores the exact original emulator scripts, removes only the
CSQ Tutorial modes it added, and preserves other tables and modes.
If an emulator script was edited after installation, uninstall deliberately
stops without changes. The original and installed scripts are retained in
the CSQGuideInstaller database table. Merge those edits with a SQLite-aware
tool or restore your backup with Popper closed. A full backup restore also
undoes any Popper changes made since that backup; do not restore it blindly.
An ordinary second install is rejected so modes/scripts cannot accumulate.

COMMAND LINE (optional)
runtime\python.exe guides.py preview --database "D:\PinUPSystem\PUPDatabase.db"
runtime\python.exe guides.py install --database "D:\PinUPSystem\PUPDatabase.db" --rotation 0 --zoom 1.35
runtime\python.exe guides.py uninstall --database "D:\PinUPSystem\PUPDatabase.db"
Add --yes only when intentionally automating approval. Install still refuses
while Popper/VPX is running. No scripts bypass this idle check.

RUNTIME / SOURCE
Python 3.13.7 Windows x64 embeddable runtime, unmodified from python.org.
The Python license is included in runtime\LICENSE.txt.
Installer source: guides.py. Mapping catalog: catalog.json.
Runtime SHA-256: f6cca216a359be84797cabb54149ce5e062afb16cc7567eb7fc51cacb2d86b65
This package is unsigned. It does not disable Windows security features.
