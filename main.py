import tkinter as tk
from tkinter import ttk, messagebox
import sys

from core.db import init_db
from ui.dashboard_view import DashboardView
from ui.pos_view import POSView
from ui.inventory_view import InventoryView
from ui.suppliers_view import SuppliersView
from ui.customers_view import CustomersView
from ui.analytics_view import AnalyticsView

class StoreManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Initialize SQLite database and sample data
        init_db()

        # Window configuration
        self.title("إدارة المتجر برو - نظام الإدارة الشامل")
        self.geometry("1280x800")
        self.minsize(1024, 700)
        self.config(bg="#1e293b")

        # Configure styles
        self._configure_styles()

        # Main layout: 2 columns (Content on Left [col 0], Sidebar on Right [col 1] for RTL)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        # 1. Main Content Container Frame (Left side)
        self.content_container = tk.Frame(self, bg="#f1f5f9")
        self.content_container.grid(row=0, column=0, sticky="nsew")
        self.content_container.columnconfigure(0, weight=1)
        self.content_container.rowconfigure(0, weight=1)

        # 2. Sidebar Navigation Frame (Right side)
        self.sidebar = tk.Frame(self, bg="#1e293b", width=230)
        self.sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.columnconfigure(0, weight=1)

        # UI views and navigation buttons
        self.nav_buttons = {}
        self.views = {}

        self._build_sidebar()
        self._init_views()

        # Start on Dashboard
        self.show_view("DashboardView")

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Treeview styling
        style.configure("Treeview",
                        background="#ffffff",
                        foreground="#0f172a",
                        rowheight=30,
                        fieldbackground="#ffffff",
                        font=("Helvetica", 11))
        style.configure("Treeview.Heading",
                        background="#f8fafc",
                        foreground="#334155",
                        font=("Helvetica", 11, "bold"),
                        relief="flat")
        style.map("Treeview",
                  background=[("selected", "#eff6ff")],
                  foreground=[("selected", "#1d4ed8")])

        # Notebook tabs styling
        style.configure("TNotebook", background="#f1f5f9", tabmargins=[0, 0, 20, 0])
        style.configure("TNotebook.Tab", background="#e2e8f0", foreground="#334155", font=("Helvetica", 11, "bold"), padding=[15, 8])
        style.map("TNotebook.Tab",
                  background=[("selected", "#ffffff")],
                  foreground=[("selected", "#2563eb")])

    def _build_sidebar(self):
        # App Title Logo Section
        logo_frame = tk.Frame(self.sidebar, bg="#0f172a", pady=20)
        logo_frame.grid(row=0, column=0, sticky="ew")
        
        lbl_logo = tk.Label(logo_frame, text="🏬 إدارة المتجر", font=("Helvetica", 18, "bold"), fg="white", bg="#0f172a")
        lbl_logo.pack()
        lbl_sub = tk.Label(logo_frame, text="نظام الإدارة الاحترافي", font=("Helvetica", 10), fg="#94a3b8", bg="#0f172a")
        lbl_sub.pack()

        # Navigation Buttons List (Arabic RTL)
        nav_items = [
            ("📊 لوحة التحكم", "DashboardView"),
            ("🛒 نقطة البيع (POS)", "POSView"),
            ("📦 المخزون والمنتجات", "InventoryView"),
            ("🚚 المورّدون والمشتريات", "SuppliersView"),
            ("👥 العملاء والولاء", "CustomersView"),
            ("📈 التحليلات والتقارير", "AnalyticsView")
        ]

        menu_frame = tk.Frame(self.sidebar, bg="#1e293b", pady=15)
        menu_frame.grid(row=1, column=0, sticky="ew")

        for i, (btn_text, view_name) in enumerate(nav_items):
            # anchor="e" for right alignment in Arabic
            btn = tk.Button(menu_frame, text=btn_text, font=("Helvetica", 12, "bold"), fg="#f8fafc", bg="#1e293b",
                            anchor="e", padx=20, pady=12, bd=0, relief="flat", cursor="hand2",
                            activebackground="#334155", activeforeground="white",
                            command=lambda v=view_name: self.show_view(v))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[view_name] = btn

        # Footer System Status
        footer_frame = tk.Frame(self.sidebar, bg="#1e293b", pady=20, padx=15)
        footer_frame.grid(row=2, column=0, sticky="s")
        self.sidebar.rowconfigure(2, weight=1)

        lbl_user = tk.Label(footer_frame, text="👤 مدير النظام", font=("Helvetica", 11, "bold"), fg="#e2e8f0", bg="#1e293b", anchor="e")
        lbl_user.pack(fill="x")
        lbl_stat = tk.Label(footer_frame, text="🟢 قاعدة البيانات متصلة", font=("Helvetica", 10), fg="#22c55e", bg="#1e293b", anchor="e")
        lbl_stat.pack(fill="x", pady=(3, 0))

        btn_exit = tk.Button(footer_frame, text="🚪 إغلاق البرنامج", font=("Helvetica", 11), fg="#f87171", bg="#1e293b",
                             anchor="e", bd=0, cursor="hand2", command=self._confirm_exit)
        btn_exit.pack(fill="x", pady=(15, 0))

    def _init_views(self):
        self.views["DashboardView"] = DashboardView(parent=self.content_container, controller=self)
        self.views["POSView"] = POSView(parent=self.content_container, controller=self)
        self.views["InventoryView"] = InventoryView(parent=self.content_container, controller=self)
        self.views["SuppliersView"] = SuppliersView(parent=self.content_container, controller=self)
        self.views["CustomersView"] = CustomersView(parent=self.content_container, controller=self)
        self.views["AnalyticsView"] = AnalyticsView(parent=self.content_container, controller=self)

        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

    def show_view(self, view_name):
        for v_name, btn in self.nav_buttons.items():
            if v_name == view_name:
                btn.config(bg="#3b82f6", fg="white", font=("Helvetica", 12, "bold"))
            else:
                btn.config(bg="#1e293b", fg="#f8fafc", font=("Helvetica", 12))

        view = self.views[view_name]
        view.refresh_data()
        view.tkraise()

    def refresh_all_views(self):
        for view in self.views.values():
            view.refresh_data()

    def _confirm_exit(self):
        if messagebox.askyesno("تأكيد الإغلاق", "هل أنت متأكد أنك تريد إغلاق برنامج إدارة المتجر برو؟"):
            self.destroy()
            sys.exit(0)

if __name__ == "__main__":
    app = StoreManagerApp()
    app.mainloop()
