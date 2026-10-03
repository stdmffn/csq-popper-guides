# Curious Side Quests — Popper Guides

A portable Windows installer that adds online pinball field guides to PinUP Popper. Select **CSQ Tutorial** on a supported table to open its guide in an Edge fullscreen cabinet viewer.

Guides stream from [Curious Side Quests](https://curioussidequests.com/pinball/). No artwork library or separate Python installation is needed.

## Download and install

Download **Curious-Side-Quests-Popper-Guides.zip** from the [latest release](https://github.com/stdmffn/csq-popper-guides/releases/latest). The GitHub source-code ZIP does not include the Windows runtime; use the named installer asset.

1. Extract the whole ZIP to a permanent folder, such as `C:\PinballGuides`.
2. Close Popper, Popper Setup, and Visual Pinball.
3. Double-click **Install.cmd** and select your `PUPDatabase.db`.
4. Review the proposed table mappings, choose rotation and zoom, and type `YES`.
5. Start Popper and choose **CSQ Tutorial** from a matched table's alternate launch options.

Keep the extracted folder in place. The default rotation is 270 degrees; choose 0 if Windows already presents your playfield upright.

Requirements: Windows 10/11 x64, Microsoft Edge, PinUP Popper with `Launch\PUPCloser.exe`, and an internet connection.

## What it changes

The installer adds a branch to the relevant VPX emulator launch/exit scripts and a **CSQ Tutorial** alternate mode to selected `.vpx` entries. Existing play modes remain intact. Multiple VPX emulator IDs are supported.

Before a change, it creates a database backup beside your Popper database in `CSQ-Guide-Backups`. Original scripts and installation metadata are stored in a `CSQGuideInstaller` table. Installation is transactional; failed changes roll back.

It does not redistribute or upload your database, table files, or local filenames. The website URL contains only the guide slug, rotation, and zoom. Edge uses a separate browser profile.

## Table matching

**Preview.cmd** writes `table-mappings.csv` without modifying Popper. Review its `Guide` column against `catalog.json`; leave a guide blank to skip a table. Apply edits with **Install mappings.cmd**.

Unknown or ambiguous matches are skipped. Some editions require an exact known filename or an explicit CSV mapping. Review matches: similarly named games can use different rules. After adding tables, uninstall and reinstall to refresh the mapping.

## Cabinet controls

| Control | Action |
| --- | --- |
| Right flipper / Right Shift | Scroll down |
| Left flipper / Left Shift | Scroll up |
| Right / left MagnaSave (Ctrl) | Next / previous section |
| Start / Enter / 1 | Open shot map, where available |
| Both MagnaSave buttons | Rotate |
| Plus / minus | Adjust reading zoom |
| Popper Exit | Close guide and return to Popper |

Common VPX gamepad mappings are also supported. Unusual controllers may need configuration.

## Uninstall

Close Popper and VPX, then run **Uninstall.cmd** against the same database. It restores the original emulator scripts and removes only the alternate modes it added, preserving unrelated table settings.

If someone edited an emulator script after installation, uninstall stops without changes rather than overwriting those edits. See [the included instructions](portable/popper-guides/README.txt) for recovery details. Restoring a complete database backup also reverts later Popper changes.

## Validation and limitations

Ten automated tests cover mapping, exact install/uninstall restoration, duplicate installation, transactional rollback, backup integrity, and preservation of subsequent changes. They passed on macOS and with the bundled Windows runtime using disposable databases.

A live Popper launch/exit cycle has not yet been verified. Edge chooses the display; this version does not force a monitor number. Check window placement and controls on your cabinet. Guides need internet access; Edge's normal media cache is not an offline installation. The package is unsigned.

## Develop and build

Run tests with Python 3:

```sh
python3 -m unittest discover -s tests/portable -v
```

Download the official [Python 3.13.7 Windows x64 embeddable runtime](https://www.python.org/ftp/python/3.13.7/python-3.13.7-embed-amd64.zip), then build:

```sh
python3 scripts/build_portable_guides.py /path/to/python-3.13.7-embed-amd64.zip
```

The builder checks the pinned runtime SHA-256 and writes the installer ZIP plus checksum to `releases/`. The runtime is included unmodified with its Python license. No packages are installed globally.

The website and its artwork are separate from this repository and are not included in the installer.
