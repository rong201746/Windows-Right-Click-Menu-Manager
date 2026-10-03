import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import winreg
import os
import sys


# ============================================================
# Registry scope definitions
# ============================================================
SCOPES = {
    "All Files (*)":        r"*",
    "Directory (folder)":   r"Directory",
    "Directory Background": r"Directory\Background",
    "Custom file type":     r"SystemFileAssociations\{ext}",
}

SCOPE_DESCRIPTIONS = {
    "All Files (*)":        r"HKEY_CLASSES_ROOT\*\shell",
    "Directory (folder)":   r"HKEY_CLASSES_ROOT\Directory\shell",
    "Directory Background": r"HKEY_CLASSES_ROOT\Directory\Background\shell",
    "Custom file type":     r"HKEY_CLASSES_ROOT\SystemFileAssociations\.<ext>\shell",
}


# ============================================================
# Core registry operations
# ============================================================
class ContextMenuManager:
    """Manage Windows right-click menu items via the registry."""

    def __init__(self):
        self.hive = winreg.HKEY_CLASSES_ROOT

    # --------------------------------------------------------
    # Build base path (without shell)
    # --------------------------------------------------------
    def _base_path(self, scope, ext=None):
        if scope == "All Files (*)":
            return r"*"
        if scope == "Directory (folder)":
            return r"Directory"
        if scope == "Directory Background":
            return r"Directory\Background"
        if scope == "Custom file type":
            if not ext:
                raise ValueError("Custom file type requires an extension.")
            ext = ext.strip()
            if not ext.startswith("."):
                ext = "." + ext
            return r"SystemFileAssociations\%s" % ext
        raise ValueError("Unknown scope: %s" % scope)

    # --------------------------------------------------------
    # Full shell path
    # --------------------------------------------------------
    def _shell_path(self, scope, ext=None):
        return self._base_path(scope, ext) + r"\shell"

    # --------------------------------------------------------
    # Open a key (read-only or read/write)
    # --------------------------------------------------------
    def _open_key(self, path, write=False):
        access = winreg.KEY_READ
        if write:
            access = winreg.KEY_READ | winreg.KEY_WRITE
        return winreg.OpenKey(self.hive, path, 0, access)

    # --------------------------------------------------------
    # List all menu items under the current scope
    # --------------------------------------------------------
    def list_items(self, scope, ext=None):
        """Return [(name, display, command), ...]"""
        results = []
        shell_path = self._shell_path(scope, ext)

        try:
            shell_key = self._open_key(shell_path)
        except FileNotFoundError:
            return results  # shell key doesn't exist, so no items yet

        try:
            index = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(shell_key, index)
                except OSError:
                    break
                index += 1

                # Skip non-menu entries (unlikely, but just in case)
                item_path = shell_path + "\\" + sub_name
                display = sub_name  # default display name is the key name
                command = ""

                try:
                    item_key = self._open_key(item_path)
                    try:
                        display, _ = winreg.QueryValueEx(item_key, "")
                    except FileNotFoundError:
                        pass

                    # Read the default value of the command subkey
                    try:
                        cmd_key = self._open_key(item_path + r"\command")
                        try:
                            command, _ = winreg.QueryValueEx(cmd_key, "")
                        except FileNotFoundError:
                            pass
                        winreg.CloseKey(cmd_key)
                    except FileNotFoundError:
                        command = "(no command key)"

                    winreg.CloseKey(item_key)
                except OSError:
                    pass

                results.append((sub_name, display, command))

        finally:
            winreg.CloseKey(shell_key)

        return results

    # --------------------------------------------------------
    # Add a menu item
    # --------------------------------------------------------
    def add_item(self, scope, key_name, display, command, ext=None):
        if not key_name:
            raise ValueError("Key name cannot be empty.")
        if not display:
            raise ValueError("Display name cannot be empty.")
        if not command:
            raise ValueError("Command cannot be empty.")

        shell_path = self._shell_path(scope, ext)
        item_path = shell_path + "\\" + key_name

        # Check if it already exists
        try:
            self._open_key(item_path)
            raise FileExistsError("A menu item with key name '%s' already exists." % key_name)
        except FileNotFoundError:
            pass

        # Create the menu item key
        item_key = winreg.CreateKey(self.hive, item_path)
        winreg.SetValueEx(item_key, "", 0, winreg.REG_SZ, display)
        winreg.CloseKey(item_key)

        # Create the command subkey
        cmd_key = winreg.CreateKey(self.hive, item_path + r"\command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
        winreg.CloseKey(cmd_key)

    # --------------------------------------------------------
    # Remove a menu item
    # --------------------------------------------------------
    def remove_item(self, scope, key_name, ext=None):
        item_path = self._shell_path(scope, ext) + "\\" + key_name

        # Delete the command subkey first
        try:
            winreg.DeleteKey(self.hive, item_path + r"\command")
        except FileNotFoundError:
            pass

        # Then delete the main key
        try:
            winreg.DeleteKey(self.hive, item_path)
        except FileNotFoundError:
            raise FileNotFoundError("Menu item '%s' not found." % key_name)

    # --------------------------------------------------------
    # Update a menu item
    # --------------------------------------------------------
    def update_item(self, scope, key_name, display, command, ext=None):
        item_path = self._shell_path(scope, ext) + "\\" + key_name

        # Update display name
        item_key = winreg.OpenKey(self.hive, item_path, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(item_key, "", 0, winreg.REG_SZ, display)
        winreg.CloseKey(item_key)

        # Update command
        cmd_key = winreg.CreateKey(self.hive, item_path + r"\command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
        winreg.CloseKey(cmd_key)


# ============================================================
# GUI application
# ============================================================
class ContextMenuGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows Right-Click Menu Manager")
        self.root.geometry("980x640")
        self.root.minsize(820, 520)

        self.mgr = ContextMenuManager()

        # Styles
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=2)

        self._build_ui()
        self._refresh_list()

    # --------------------------------------------------------
    # Build the UI
    # --------------------------------------------------------
    def _build_ui(self):
        # Top: scope selection
        top_frame = ttk.Frame(self.root, padding=(12, 10, 12, 6))
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="Scope:").pack(side="left", padx=(0, 6))
        self.scope_var = tk.StringVar(value="All Files (*)")
        self.scope_combo = ttk.Combobox(
            top_frame,
            textvariable=self.scope_var,
            values=list(SCOPES.keys()),
            state="readonly",
            width=24,
        )
        self.scope_combo.pack(side="left")
        self.scope_combo.bind("<<ComboboxSelected>>", lambda e: self._on_scope_change())

        # Extension entry (only for Custom file type)
        ttk.Label(top_frame, text="Extension:").pack(side="left", padx=(18, 6))
        self.ext_var = tk.StringVar(value=".py")
        self.ext_entry = ttk.Entry(top_frame, textvariable=self.ext_var, width=12)
        self.ext_entry.pack(side="left")
        self.ext_entry.configure(state="disabled")

        # Path display
        ttk.Label(top_frame, text="Registry path:").pack(side="left", padx=(18, 6))
        self.path_var = tk.StringVar()
        path_label = ttk.Label(
            top_frame,
            textvariable=self.path_var,
            foreground="#475569",
            font=("Consolas", 9),
        )
        path_label.pack(side="left", fill="x", expand=True)

        # Middle: menu item list
        mid_frame = ttk.Frame(self.root, padding=(12, 6, 12, 6))
        mid_frame.pack(fill="both", expand=True)

        columns = ("key", "display", "command")
        self.tree = ttk.Treeview(
            mid_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("key", text="Key Name")
        self.tree.heading("display", text="Display Name")
        self.tree.heading("command", text="Command")
        self.tree.column("key", width=160, anchor="w")
        self.tree.column("display", width=200, anchor="w")
        self.tree.column("command", width=520, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(mid_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self._on_edit())

        # Bottom: form + buttons
        bottom_frame = ttk.LabelFrame(self.root, text="Menu item details", padding=(12, 8, 12, 10))
        bottom_frame.pack(fill="x", padx=12, pady=(0, 10))

        # Row 1: Key + Display
        row1 = ttk.Frame(bottom_frame)
        row1.pack(fill="x", pady=2)

        ttk.Label(row1, text="Key name:", width=12).pack(side="left")
        self.key_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.key_var, width=28).pack(side="left", padx=(0, 16))

        ttk.Label(row1, text="Display name:", width=14).pack(side="left")
        self.display_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.display_var, width=36).pack(side="left", fill="x", expand=True)

        # Row 2: Command
        row2 = ttk.Frame(bottom_frame)
        row2.pack(fill="x", pady=2)

        ttk.Label(row2, text="Command:", width=12).pack(side="left")
        self.command_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.command_var).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row2, text="Browse...", command=self._browse_command).pack(side="left")

        # Row 3: action buttons
        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(btn_frame, text="Add", command=self._on_add, width=14).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Update", command=self._on_update, width=14).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Remove", command=self._on_remove, width=14).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_list, width=14).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Clear form", command=self._clear_form, width=14).pack(side="left", padx=3)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(6, 3))
        status.pack(fill="x", side="bottom")

        # Initial path display
        self._update_path_label()

    # --------------------------------------------------------
    # UI event handlers
    # --------------------------------------------------------
    def _on_scope_change(self):
        scope = self.scope_var.get()
        if scope == "Custom file type":
            self.ext_entry.configure(state="normal")
        else:
            self.ext_entry.configure(state="disabled")
        self._update_path_label()
        self._refresh_list()

    def _update_path_label(self):
        scope = self.scope_var.get()
        ext = self.ext_var.get().strip() if scope == "Custom file type" else None
        try:
            full = "HKEY_CLASSES_ROOT\\" + self.mgr._shell_path(scope, ext)
        except Exception as e:
            full = str(e)
        self.path_var.set(full)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        if not values:
            return
        key, display, command = values
        self.key_var.set(key)
        self.display_var.set(display)
        self.command_var.set(command)

    def _on_edit(self):
        self._on_update()

    def _clear_form(self):
        self.key_var.set("")
        self.display_var.set("")
        self.command_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def _browse_command(self):
        """Let the user pick an executable and auto-fill the command."""
        path = filedialog.askopenfilename(
            title="Select executable",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            # Wrap in quotes and append %1 (or %V for directory background)
            scope = self.scope_var.get()
            placeholder = "%V" if scope == "Directory Background" else "%1"
            self.command_var.set('"%s" %s' % (path, placeholder))

    # --------------------------------------------------------
    # CRUD operations
    # --------------------------------------------------------
    def _refresh_list(self):
        scope = self.scope_var.get()
        ext = self.ext_var.get().strip() if scope == "Custom file type" else None

        # Clear
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            items = self.mgr.list_items(scope, ext)
            for key, display, command in items:
                self.tree.insert("", "end", values=(key, display, command))
            self.status_var.set("Loaded %d item(s)." % len(items))
        except Exception as e:
            self.status_var.set("Error: %s" % e)
            messagebox.showerror("Error", str(e))

        self._update_path_label()

    def _on_add(self):
        scope = self.scope_var.get()
        ext = self.ext_var.get().strip() if scope == "Custom file type" else None
        key = self.key_var.get().strip()
        display = self.display_var.get().strip()
        command = self.command_var.get().strip()

        try:
            self.mgr.add_item(scope, key, display, command, ext)
            self.status_var.set("Added '%s'." % key)
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Add failed", str(e))
            self.status_var.set("Add failed: %s" % e)

    def _on_update(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Update", "Please select an item to update.")
            return

        old_key = self.tree.item(sel[0], "values")[0]
        scope = self.scope_var.get()
        ext = self.ext_var.get().strip() if scope == "Custom file type" else None
        new_key = self.key_var.get().strip()
        display = self.display_var.get().strip()
        command = self.command_var.get().strip()

        if not new_key:
            messagebox.showwarning("Update", "Key name cannot be empty.")
            return

        try:
            if new_key != old_key:
                # Key name changed: delete old, then add new
                self.mgr.remove_item(scope, old_key, ext)
                self.mgr.add_item(scope, new_key, display, command, ext)
            else:
                self.mgr.update_item(scope, old_key, display, command, ext)
            self.status_var.set("Updated '%s'." % new_key)
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Update failed", str(e))
            self.status_var.set("Update failed: %s" % e)

    def _on_remove(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Remove", "Please select an item to remove.")
            return

        key = self.tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("Confirm removal",
                                   "Delete menu item '%s'?\nThis cannot be undone." % key):
            return

        scope = self.scope_var.get()
        ext = self.ext_var.get().strip() if scope == "Custom file type" else None

        try:
            self.mgr.remove_item(scope, key, ext)
            self.status_var.set("Removed '%s'." % key)
            self._clear_form()
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Remove failed", str(e))
            self.status_var.set("Remove failed: %s" % e)


# ============================================================
# Entry point
# ============================================================
def main():
    # Request administrator privileges (if possible)
    if sys.platform == "win32":
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                # Re-launch with administrator privileges
                params = " ".join(['"%s"' % arg for arg in sys.argv])
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, params, None, 1
                )
                sys.exit(0)
        except Exception:
            pass  # If elevation fails, continue anyway (read-only operations still work)

    root = tk.Tk()
    app = ContextMenuGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
