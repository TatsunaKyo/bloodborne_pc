# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Launcher dialog for inspecting a support report before a local export."""
from datetime import datetime
from pathlib import Path
import threading
import webbrowser

import support_report


class SupportReportDialog:
    def __init__(self, launcher):
        self.launcher, self.report, self.generation = launcher, None, 0
        tk, ttk = launcher.tk, launcher.ttk
        self.window = tk.Toplevel(launcher.root)
        self.window.title('The Crowned Workshop — Support Report')
        self.window.configure(bg='#171412')
        self.window.transient(launcher.root)
        width = min(launcher.px(900), launcher.root.winfo_screenwidth() - 60)
        height = min(launcher.px(650), launcher.root.winfo_screenheight() - 100)
        self.window.geometry(f'{width}x{height}')
        self.window.minsize(launcher.px(640), launcher.px(480))
        body = ttk.Frame(self.window, padding=launcher.px(16))
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1); body.rowconfigure(3, weight=1)
        ttk.Label(body, text='Generate Support Report', font=('Georgia', 20)).grid(row=0, column=0, sticky='w')
        self.description = ttk.Label(body, text='Inspect the sanitized files before exporting. Game files, saves, credentials and memory dumps are excluded. Nothing is uploaded.',
                                     style='Muted.TLabel', justify='left', wraplength=width - launcher.px(40))
        self.description.grid(row=1, column=0, sticky='we', pady=(8, 12))
        options = ttk.Frame(body); options.grid(row=2, column=0, sticky='we', pady=(0, 12))
        self.logs, self.profile = tk.BooleanVar(value=True), tk.BooleanVar(value=False)
        self.logs_control = ttk.Checkbutton(options, text='Include recent sanitized logs', variable=self.logs, command=self.refresh)
        self.logs_control.pack(anchor='w')
        self.profile_control = ttk.Checkbutton(options, text='Include anonymous CPU / RAM profile',
                                              variable=self.profile, command=self.refresh)
        self.profile_control.pack(anchor='w', pady=(5, 0))
        pane = ttk.Panedwindow(body, orient='horizontal'); pane.grid(row=3, column=0, sticky='nsew')
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=1); pane.add(right, weight=3)
        self.files = ttk.Treeview(left, columns=('bytes',), show='tree headings', selectmode='browse',
                                  style='Workshop.Treeview')
        self.files.heading('#0', text='Included files'); self.files.heading('bytes', text='Bytes')
        self.files.column('#0', width=launcher.px(230), minwidth=launcher.px(100))
        self.files.column('bytes', width=launcher.px(65), minwidth=launcher.px(50), stretch=False, anchor='e')
        self.files.pack(fill='both', expand=True)
        self.files.bind('<<TreeviewSelect>>', self.inspect)
        self.preview = tk.Text(right, wrap='word', state='disabled', bg='#0a0908', fg='#cfc6b8',
                               font=('Consolas', 9), relief='flat', padx=8, pady=8, width=40)
        scrollbar = ttk.Scrollbar(right, command=self.preview.yview)
        self.preview.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y'); self.preview.pack(fill='both', expand=True)
        self.status = tk.StringVar(value='Collecting existing diagnostics…')
        self.status_label = ttk.Label(body, textvariable=self.status, style='Muted.TLabel', wraplength=width - launcher.px(40))
        self.status_label.grid(row=4, column=0, sticky='we', pady=(10, 8))
        actions = ttk.Frame(body); actions.grid(row=5, column=0, sticky='we')
        self.export_button = ttk.Button(actions, text='Export ZIP…', command=self.export, state='disabled')
        self.export_button.pack(side='right')
        ttk.Button(actions, text='Close', command=self.window.destroy).pack(side='right', padx=(0, 8))
        ttk.Button(actions, text='Refresh', command=self.refresh).pack(side='left')
        self.copy_button = ttk.Button(actions, text='Copy summary', command=self.copy, state='disabled')
        self.copy_button.pack(side='left', padx=8)
        issue_actions = ttk.Frame(body); issue_actions.grid(row=6, column=0, sticky='w', pady=(10, 0))
        ttk.Button(issue_actions, text='Open bug form', command=lambda: self.issue('bug-report.yml')).pack(side='left')
        ttk.Button(issue_actions, text='Open performance form', command=lambda: self.issue('performance-regression.yml')).pack(side='left', padx=8)
        body.bind('<Configure>', lambda event: (self.description.configure(wraplength=max(240, event.width - 32)),
                                                self.status_label.configure(wraplength=max(240, event.width - 32))))
        self.refresh()

    def deliver(self, callback):
        self.launcher.ui_calls.put(lambda: callback() if self.window.winfo_exists() else None)

    def set_preview(self, text):
        self.preview.configure(state='normal'); self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', text); self.preview.configure(state='disabled')

    def refresh(self):
        self.generation += 1
        generation = self.generation
        self.report = None
        self.files.delete(*self.files.get_children()); self.set_preview('')
        self.export_button.configure(state='disabled'); self.copy_button.configure(state='disabled')
        self.status.set('Collecting and sanitizing existing diagnostics…')
        context = self.launcher.support_report_context()
        logs, profile = self.logs.get(), self.profile.get()

        def collect():
            try:
                report = support_report.build_report(**context, include_logs=logs, include_profile=profile)
            except Exception as error:
                self.deliver(lambda message=str(error): self.failed(generation, message))
            else:
                self.deliver(lambda: self.ready(generation, report))
        threading.Thread(target=collect, daemon=True).start()

    def failed(self, generation, message):
        if generation == self.generation:
            self.status.set('Could not collect the report: ' + message)

    def ready(self, generation, report):
        if generation != self.generation:
            return
        self.report = report
        for name, data in sorted(report.entries.items()):
            self.files.insert('', 'end', iid=name, text=name, values=(len(data),))
        self.files.selection_set('report-summary.md'); self.inspect()
        self.export_button.configure(state='normal'); self.copy_button.configure(state='normal')
        self.status.set(' '.join(report.warnings) if report.warnings else
                        'Ready to inspect. The optional hardware submission remains unreviewed.')

    def inspect(self, _event=None):
        selected = self.files.selection()
        if self.report and selected:
            self.set_preview(self.report.entries[selected[0]].decode('utf-8', errors='replace'))

    def copy(self):
        if self.report:
            self.window.clipboard_clear(); self.window.clipboard_append(self.report.summary)
            self.status.set('Sanitized summary copied. Add reproduction steps in the issue form.')

    def issue(self, template):
        webbrowser.open(support_report.REPOSITORY + '/issues/new?template=' + template)

    def export(self):
        if not self.report:
            return
        destination = self.launcher.filedialog.asksaveasfilename(parent=self.window,
            title='Export inspected Support Report', defaultextension='.zip',
            initialfile='Crowned-Workshop-Support-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.zip',
            filetypes=[('ZIP archive', '*.zip')])
        if not destination:
            return
        report = self.report
        try:
            support_report.export_report(report, Path(destination))
        except (OSError, ValueError, RuntimeError) as error:
            self.launcher.messagebox.showerror('Support Report', str(error), parent=self.window)
        else:
            self.status.set('ZIP exported and verified. Attach it manually after reviewing the issue details.')


def open_support_report(launcher):
    existing = getattr(launcher, 'support_dialog', None)
    if existing and existing.window.winfo_exists():
        existing.window.lift(); existing.window.focus_set()
        return existing
    launcher.support_dialog = SupportReportDialog(launcher)
    return launcher.support_dialog
