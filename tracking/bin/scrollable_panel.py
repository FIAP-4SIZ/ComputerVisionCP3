"""Área rolável compartilhada pelas duas telas Tk; sem dependências extras."""
import tkinter as tk
from tkinter import ttk


class ScrollablePanel(tk.Frame):
    def __init__(self, window):
        super().__init__(window)
        self.pack(fill='both', expand=True)
        window.maxsize(window.winfo_screenwidth(), max(200, window.winfo_screenheight()-60))
        self.canvas = tk.Canvas(self, highlightthickness=0,
                                width=min(700, window.winfo_screenwidth()-60),
                                height=min(850, max(200, window.winfo_screenheight()-140)))
        vertical = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.content = tk.Frame(self.canvas)
        self.item = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self.content.bind('<Configure>', self._content_changed)
        self.canvas.bind('<Configure>', self._canvas_changed)
        window.bind('<MouseWheel>', self._wheel, add='+')
        window.bind('<Button-4>', lambda event: self.canvas.yview_scroll(-1, 'units'), add='+')
        window.bind('<Button-5>', lambda event: self.canvas.yview_scroll(1, 'units'), add='+')
        window.bind('<Next>', lambda event: self.canvas.yview_scroll(1, 'pages'), add='+')
        window.bind('<Prior>', lambda event: self.canvas.yview_scroll(-1, 'pages'), add='+')

    def _content_changed(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _canvas_changed(self, event):
        self.canvas.itemconfigure(self.item, width=max(event.width, self.content.winfo_reqwidth()))

    def _wheel(self, event):
        # Windows usa múltiplos de 120; trackpads/macOS podem enviar ±1.
        if event.delta:
            units = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
            self.canvas.yview_scroll(units, 'units')
