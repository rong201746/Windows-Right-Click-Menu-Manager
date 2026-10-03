# Windows Right-Click Menu Manager

A Python GUI tool for managing Windows right-click (context menu) entries by directly editing the registry. Built with `tkinter` and `winreg`, it provides a safe and intuitive way to add, update, and remove custom shell menu items across four common scopes.

---

## Features

- **Four registry scopes supported:**
  - All Files (`HKEY_CLASSES_ROOT\*\shell`)
  - Directory / Folder (`HKEY_CLASSES_ROOT\Directory\shell`)
  - Directory Background (`HKEY_CLASSES_ROOT\Directory\Background\shell`)
  - Custom file type (`HKEY_CLASSES_ROOT\SystemFileAssociations\.<ext>\shell`)
- **Full CRUD operations:** Add, update, and remove menu items with automatic creation and cleanup of the required `command` subkey.
- **Live registry browsing:** The item list is read directly from the registry and refreshes on demand.
- **Command builder:** Pick an executable with a file dialog and automatically wrap it in quotes with the correct placeholder (`%1` or `%V`).
- **Correct placeholder handling:** `%V` is used automatically for Directory Background scope, `%1` for all others.
- **Automatic elevation:** The script attempts to re-launch itself with administrator privileges on Windows, since writing to `HKEY_CLASSES_ROOT` normally requires it.
- **Clear status feedback:** A status bar reports the result of every operation.

---

## Requirements

- **OS:** Windows (uses `winreg` and `ctypes`)
- **Python:** 3.6 or newer
- **Dependencies:** None beyond the Python standard library (`tkinter`, `winreg`, `ctypes`)

> `tkinter` is included with standard Python installers on Windows. If it is missing, reinstall Python with the "tcl/tk and IDLE" option checked.

---

## Installation

1. Make sure Python 3.6+ is installed on Windows.
2. Save the script as `context_menu_manager.py`.
3. No third-party packages are required.

---

## Usage

Run the script from a terminal:

```bash
python context_menu_manager.py
```

A UAC prompt will appear if the current session does not have administrator privileges. Accept it to allow write operations.

### Interface overview

| Area | Purpose |
|------|---------|
| **Scope** dropdown | Select which registry scope to manage. |
| **Extension** field | Enabled only when *Custom file type* is selected (e.g. `.py`, `.txt`). |
| **Registry path** label | Shows the exact `HKEY_CLASSES_ROOT` path currently in use. |
| **Item table** | Lists all menu items under the selected scope (Key Name, Display Name, Command). |
| **Details form** | Edit the key name, display name, and command of the selected or new item. |
| **Action buttons** | Add, Update, Remove, Refresh, and Clear form. |

### Typical workflow

**Add a menu item**

1. Choose a scope, for example *Directory (folder)*.
2. Fill in the *Key name* (internal identifier, no spaces preferred).
3. Fill in the *Display name* (text shown in the context menu).
4. Click **Browse...** to pick an executable, or type the command manually. Use `%1` (file/folder path) or `%V` (background folder path) as the argument placeholder.
5. Click **Add**. The item appears in the table immediately.

**Update a menu item**

1. Click a row in the table to load its values into the form.
2. Modify the display name, command, or even the key name.
3. Click **Update**. If the key name changed, the old key is removed and a new one is created.

**Remove a menu item**

1. Select the row you want to delete.
2. Click **Remove** and confirm the prompt.

---

## Registry Paths Reference

| Scope label in UI | Registry path |
|-------------------|---------------|
| All Files (*) | `HKEY_CLASSES_ROOT\*\shell` |
| Directory (folder) | `HKEY_CLASSES_ROOT\Directory\shell` |
| Directory Background | `HKEY_CLASSES_ROOT\Directory\Background\shell` |
| Custom file type | `HKEY_CLASSES_ROOT\SystemFileAssociations\.<ext>\shell` |

For each menu item, the tool creates:

```
<shell_path>\<KeyName>              (default value = Display Name)
<shell_path>\<KeyName>\command      (default value = Command string)
```

---

## Placeholder Reference

| Placeholder | Meaning | Used in |
|-------------|---------|---------|
| `%1` | Full path of the file or folder that was right-clicked | All Files, Directory, Custom file type |
| `%V` | Full path of the current folder (the background) | Directory Background |

Example command for opening a file with Notepad:

```
"C:\Windows\notepad.exe" "%1"
```

Example command for opening a terminal in the current folder:

```
"C:\Windows\System32\cmd.exe" /k cd /d "%V"
```

---

## Safety Notes

- **Administrator rights:** Writing to `HKEY_CLASSES_ROOT` typically requires elevation. The script will try to re-launch itself elevated; if that fails, read-only browsing still works.
- **Back up first:** Registry edits are not easily reversible. Before experimenting, export the relevant keys with `regedit` or create a System Restore point.
- **Use exact key names:** Deleting a key that you did not create may break other applications' context menu entries.
- **Windows 11:** The modern Windows 11 context menu may hide classic `shell` entries behind "Show more options". This is a Windows design choice, not a limitation of this tool.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `PermissionError` or `Access is denied` when adding/removing | Not running as administrator | Run the script from an elevated terminal, or accept the UAC prompt. |
| New menu item does not appear | Windows 11 collapsed menu | Click "Show more options" or press `Shift+F10`. |
| `FileNotFoundError` for the shell path | No items exist under that scope yet | That is normal; add one to create the path. |
| `tkinter` import error | Python installed without tcl/tk | Reinstall Python and enable the tcl/tk component. |
| Changes not visible immediately | Explorer cached the menu | Sign out and back in, or restart `explorer.exe`. |

---

## Code Structure

```
context_menu_manager.py
├── SCOPES / SCOPE_DESCRIPTIONS   # Scope label → registry path mapping
├── ContextMenuManager            # Registry CRUD logic (winreg)
│   ├── _base_path()
│   ├── _shell_path()
│   ├── _open_key()
│   ├── list_items()
│   ├── add_item()
│   ├── remove_item()
│   └── update_item()
├── ContextMenuGUI                # Tkinter interface
│   ├── _build_ui()
│   ├── _on_scope_change()
│   ├── _refresh_list()
│   ├── _on_add()
│   ├── _on_update()
│   └── _on_remove()
└── main()                        # UAC elevation + app start
```

---

## License

This project is provided as-is for personal and educational use. Use it at your own risk; always back up your registry before making changes.
