# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Closed-game save management, integrated with the launcher's selected saves folder."""
from pathlib import Path
import threading

from save_manager import SaveManager, verify_backup


class SaveManagerDialog:
    def __init__(self, launcher):
        self.launcher, self.busy, self.records = launcher, False, {}
        # The destination is fixed for this dialog, even if the main window's
        # selected folder changes while a worker is using it.
        self.manager = SaveManager(launcher.support_report_context()['user_dir'])
        tk, ttk = launcher.tk, launcher.ttk
        self.window = tk.Toplevel(launcher.root)
        self.window.title('The Crowned Workshop — Save Manager')
        self.window.configure(bg='#171412'); self.window.transient(launcher.root)
        width = min(launcher.px(900), launcher.root.winfo_screenwidth() - 60)
        height = min(launcher.px(650), launcher.root.winfo_screenheight() - 100)
        self.window.geometry(f'{width}x{height}'); self.window.minsize(launcher.px(640), launcher.px(500))
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        body = ttk.Frame(self.window, padding=launcher.px(16)); body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1); body.rowconfigure(3, weight=1)
        ttk.Label(body, text='Save Manager', font=('Georgia', 20)).grid(row=0, column=0, sticky='w')
        self.description = ttk.Label(body, text='Create and restore snapshots with the game closed. Pausing rendering still leaves the game active.',
                                     style='Muted.TLabel', wraplength=width - launcher.px(40))
        self.description.grid(row=1, column=0, sticky='we', pady=(6, 8))
        self.source_label = ttk.Label(body, text='Saves folder: ' + str(self.manager.root), wraplength=width - launcher.px(40))
        self.source_label.grid(row=2, column=0, sticky='we', pady=(0, 10))
        tabs = ttk.Notebook(body); tabs.grid(row=3, column=0, sticky='nsew')
        style = ttk.Style(launcher.root)
        style.configure('Workshop.TNotebook', background='#171412', borderwidth=0)
        style.configure('Workshop.TNotebook.Tab', background='#221c16', foreground='#cfc6b8', padding=(12, 6))
        style.map('Workshop.TNotebook.Tab', background=[('selected', '#342819')], foreground=[('selected', '#d4bb83')])
        tabs.configure(style='Workshop.TNotebook')
        snapshots, backup_options = ttk.Frame(tabs, padding=8), ttk.Frame(tabs, padding=12)
        tabs.add(snapshots, text='Snapshots'); tabs.add(backup_options, text='Backup options')
        snapshots.columnconfigure(0, weight=1); snapshots.rowconfigure(0, weight=1)
        self.tabs = tabs
        options = ttk.Frame(backup_options); options.pack(fill='x')
        self.auto_control = ttk.Checkbutton(options, text='Back up existing saves before each launch',
                                            variable=launcher.var('save_auto_backup', 'app'))
        self.auto_control.grid(row=0, column=0, columnspan=3, sticky='w')
        ttk.Label(options, text='Automatic snapshots to keep:').grid(row=1, column=0, sticky='w', pady=6)
        self.retention = ttk.Spinbox(options, from_=1, to=100, increment=1, width=5,
                                     textvariable=launcher.var('save_backup_retention', 'app'))
        self.retention.grid(row=1, column=1, sticky='w', padx=(8, 0))
        self.retention.bind('<FocusOut>', self.validate_retention); self.retention.bind('<Return>', self.validate_retention)
        ttk.Label(options, text='Manual and rollback snapshots are kept.', style='Muted.TLabel').grid(row=2, column=0, columnspan=3, sticky='w')
        listing = ttk.Frame(snapshots); listing.grid(row=0, column=0, sticky='nsew')
        self.files = ttk.Treeview(listing, columns=('created', 'kind', 'status'), show='tree headings', selectmode='browse',
                                  style='Workshop.Treeview')
        for key, text in (('#0', 'Snapshot'), ('created', 'Created (UTC)'), ('kind', 'Type'), ('status', 'Integrity')):
            self.files.heading(key, text=text)
        for key, size in (('#0', 235), ('created', 160), ('kind', 75), ('status', 90)):
            self.files.column(key, width=launcher.px(size), minwidth=launcher.px(50))
        vertical = ttk.Scrollbar(listing, command=self.files.yview)
        horizontal = ttk.Scrollbar(listing, orient='horizontal', command=self.files.xview)
        self.files.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        horizontal.pack(side='bottom', fill='x'); vertical.pack(side='right', fill='y'); self.files.pack(fill='both', expand=True)
        self.files.bind('<<TreeviewSelect>>', self.selection_changed)
        self.details = tk.StringVar(value='Only complete, verified archives can be restored.')
        self.details_label = ttk.Label(snapshots, textvariable=self.details, style='Muted.TLabel', wraplength=width - launcher.px(40))
        self.details_label.grid(row=1, column=0, sticky='we', pady=(8, 6))
        named = ttk.Frame(snapshots); named.grid(row=2, column=0, sticky='we'); named.columnconfigure(1, weight=1)
        ttk.Label(named, text='Snapshot name:').grid(row=0, column=0, sticky='w')
        self.name = tk.StringVar(value='Before the next boss')
        self.name_entry = ttk.Entry(named, textvariable=self.name); self.name_entry.grid(row=0, column=1, sticky='we', padx=8)
        self.snapshot_button = ttk.Button(named, text='Create snapshot', command=self.snapshot)
        self.snapshot_button.grid(row=0, column=2, sticky='e')
        actions = ttk.Frame(snapshots); actions.grid(row=3, column=0, sticky='we', pady=(10, 0))
        self.restore_button = ttk.Button(actions, text='Restore selected…', command=self.restore, state='disabled')
        self.restore_button.pack(side='left')
        self.import_button = ttk.Button(actions, text='Import backup…', command=self.import_backup)
        self.import_button.pack(side='left', padx=8)
        self.refresh_button = ttk.Button(actions, text='Refresh', command=self.refresh); self.refresh_button.pack(side='left')
        self.close_button = ttk.Button(actions, text='Close', command=self.close); self.close_button.pack(side='right')
        extra = ttk.Frame(snapshots); extra.grid(row=4, column=0, sticky='we', pady=(8, 0))
        self.recovery_button = ttk.Button(extra, text='Recover interrupted restore', command=self.recover)
        self.recovery_button.pack(side='left')
        ttk.Button(extra, text='Open backups folder', command=lambda: launcher.open_path(self.manager.backups)).pack(side='left', padx=8)
        self.status = tk.StringVar(value='Checking backup integrity…')
        self.status_label = ttk.Label(body, textvariable=self.status, style='Muted.TLabel', wraplength=width - launcher.px(40))
        self.status_label.grid(row=4, column=0, sticky='we', pady=(10, 0))
        body.bind('<Configure>', lambda event: [w.configure(wraplength=max(240, event.width - 32))
                    for w in (self.description, self.source_label, self.details_label, self.status_label)])
        self.refresh()

    def validate_retention(self, _event=None):
        value = self.launcher.var('save_backup_retention', 'app')
        try:
            count = max(1, min(100, int(value.get())))
        except ValueError:
            count = 10
        value.set(str(count))

    def set_busy(self, busy):
        self.busy = busy
        self.launcher.save_busy = busy
        for widget in (self.import_button, self.refresh_button, self.close_button):
            widget.configure(state='disabled' if busy else 'normal')
        for widget in (self.snapshot_button, self.recovery_button):
            widget.configure(state='disabled' if busy or self.launcher.process else 'normal')
        self.restore_button.configure(state='disabled')
        if not self.launcher.ui_closed:
            self.launcher.refresh_status()
        if not busy:
            self.selection_changed()

    def run(self, description, operation, completion):
        if self.busy:
            return
        self.set_busy(True); self.status.set(description)
        def work():
            try:
                result = operation()
            except Exception as error:
                self.launcher.ui_calls.put(lambda message=str(error): self.finished(None, completion, message))
            else:
                self.launcher.ui_calls.put(lambda: self.finished(result, completion, None))
        # Keep a normal close from terminating a file transaction. A forced
        # process exit is handled by the restore journal on the next launch.
        threading.Thread(target=work, daemon=False).start()

    def finished(self, result, completion, error):
        self.launcher.save_busy = False
        if self.launcher.ui_closed:
            return
        if not self.window.winfo_exists():
            self.launcher.refresh_status(); return
        self.set_busy(False)
        if error:
            self.status.set(error)
            self.launcher.messagebox.showerror('Save Manager', error, parent=self.window)
        else:
            completion(result)

    def refresh(self):
        self.run('Verifying snapshot contents and checksums…', self.manager.list_snapshots, self.list_ready)

    def list_ready(self, records):
        self.files.delete(*self.files.get_children()); self.records = {}
        for index, record in enumerate(records):
            key = str(index); self.records[key] = record
            if record['status'] == 'verified':
                data = record['manifest']
                values = (data['created_utc'].replace('T', ' ')[:19], data['category'], 'Verified')
                label = data['label']
            else:
                label, values = record['path'].name, ('—', '—', 'Invalid')
            self.files.insert('', 'end', iid=key, text=label, values=values)
        self.status.set(f'{len(records)} archives checked. Manual and rollback snapshots are outside automatic retention.')

    def selection_changed(self, _event=None):
        selected = self.files.selection()
        record = self.records.get(selected[0]) if selected else None
        valid = record is not None and record['status'] == 'verified'
        self.restore_button.configure(state='normal' if valid and not self.busy and not self.launcher.process else 'disabled')
        if valid:
            data = record['manifest']; size = sum(f['size'] for f in data['files'])
            self.details.set(f"{data['label']} — {len(data['files'])} files, {size:,} bytes. Metadata and save memory are included.")
        elif record:
            self.details.set(record['error'])

    def snapshot(self):
        if self.busy or self.launcher.process:
            return
        label = self.name.get().strip() or 'Manual snapshot'
        self.run('Creating and verifying the named snapshot…', lambda: self.manager.snapshot(label),
                 lambda _path: self.refresh())

    def restore(self):
        selected = self.files.selection()
        record = self.records.get(selected[0]) if selected else None
        if not record or record['status'] != 'verified':
            return
        self.restore_path(record['path'], record['manifest'])

    def restore_path(self, path, manifest):
        if self.busy or self.launcher.process:
            return
        foreign = manifest['root_id'] != self.manager.root_id
        message = f'Restore "{manifest["label"]}" to:\n{self.manager.root}\n\nYour current saves will be kept in a verified rollback snapshot.'
        if foreign:
            message += '\n\nThis backup comes from another saves folder. Import it into this selected folder?'
        if not self.launcher.messagebox.askyesno('Restore saves', message, parent=self.window):
            return
        self.run('Preparing verified saves and a rollback copy…',
                 lambda: self.manager.restore(path, allow_other_folder=foreign), lambda _result: self.refresh())

    def import_backup(self):
        path = self.launcher.filedialog.askopenfilename(parent=self.window, title='Inspect save backup for import',
                        filetypes=[('Save backup ZIP', '*.zip')])
        if not path:
            return
        self.run('Verifying the imported archive before restoration…', lambda: verify_backup(Path(path)),
                 lambda manifest: self.restore_path(Path(path), manifest))

    def recover(self):
        self.run('Checking and recovering the interrupted restore…', self.manager.recover,
                 lambda message: (self.status.set(message or 'No interrupted restore needs recovery.'), self.refresh()))

    def close(self):
        if not self.busy:
            self.validate_retention(); self.window.destroy()


def open_save_manager(launcher):
    dialog = getattr(launcher, 'save_dialog', None)
    if dialog and dialog.window.winfo_exists():
        selected = Path(launcher.support_report_context()['user_dir']).resolve()
        if dialog.busy or dialog.manager.root == selected:
            dialog.window.lift(); dialog.window.focus_set(); return dialog
        dialog.window.destroy()
    launcher.save_dialog = SaveManagerDialog(launcher)
    return launcher.save_dialog
