import tkinter as tk
from tkinter import ttk

from core.db import get_dashboard_summary, get_recent_sales, get_sale_details


class DashboardView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.metric_labels = {}

        header_frame = tk.Frame(self, bg="#f1f5f9")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        tk.Label(header_frame, text="لوحة تحكم المتجر", font=("Helvetica", 24, "bold"), fg="#0f172a", bg="#f1f5f9").pack(side="right")

        quick_frame = tk.Frame(header_frame, bg="#f1f5f9")
        quick_frame.pack(side="left")
        tk.Button(quick_frame, text="📦 إضافة منتج جديد", font=("Helvetica", 11, "bold"), bg="#16a34a", fg="white", padx=15, pady=6, bd=0, cursor="hand2", command=lambda: self.controller.show_view("InventoryView")).pack(side="right", padx=5)
        tk.Button(quick_frame, text="🛒 بدء عملية بيع", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white", padx=15, pady=6, bd=0, cursor="hand2", command=lambda: self.controller.show_view("POSView")).pack(side="right", padx=5)

        self.metrics_frame = tk.Frame(self, bg="#f1f5f9")
        self.metrics_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.metrics_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self._build_metric_cards()

        sales_section = tk.Frame(self, bg="white", padx=15, pady=15)
        sales_section.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        sales_section.columnconfigure(0, weight=1)
        sales_section.rowconfigure(1, weight=1)

        sec_header = tk.Frame(sales_section, bg="white")
        sec_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tk.Label(sec_header, text="أحدث العمليات والفواتير", font=("Helvetica", 18, "bold"), fg="#0f172a", bg="white").pack(side="right")
        tk.Button(sec_header, text="🔄 تحديث البيانات", font=("Helvetica", 11), bg="#e2e8f0", fg="#0f172a", padx=12, pady=4, bd=0, cursor="hand2", command=self.refresh_data).pack(side="left")

        columns = ("id", "date", "customer", "amount", "payment")
        self.sales_tree = ttk.Treeview(sales_section, columns=columns, show="headings", height=12)
        self.sales_tree.heading("id", text="رقم الفاتورة")
        self.sales_tree.heading("date", text="التاريخ والوقت")
        self.sales_tree.heading("customer", text="اسم العميل")
        self.sales_tree.heading("amount", text="المبلغ الإجمالي")
        self.sales_tree.heading("payment", text="طريقة الدفع")

        self.sales_tree.column("id", width=90, anchor="center")
        self.sales_tree.column("date", width=180, anchor="center")
        self.sales_tree.column("customer", width=220, anchor="e")
        self.sales_tree.column("amount", width=120, anchor="center")
        self.sales_tree.column("payment", width=160, anchor="center")

        scrollbar = ttk.Scrollbar(sales_section, orient="vertical", command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=scrollbar.set)
        self.sales_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        self.sales_tree.bind("<Double-1>", self._on_sale_double_click)

        tk.Label(sales_section, text="* انقر مرتين على أي صف في الجدول لعرض إيصال تفاصيل الفاتورة والمشتريات.", font=("Helvetica", 10, "italic"), fg="#64748b", bg="white").grid(row=2, column=0, sticky="e", pady=(10, 0))

        self.refresh_data()

    def _build_metric_cards(self):
        cards = [
            ("حالة الجلسة الحالية", "session_status", "#0f172a"),
            ("الرصيد النقدي المتوقع", "expected_cash", "#2563eb"),
            ("مبيعات اليوم", "sales_today", "#16a34a"),
            ("صافي مبيعات اليوم", "net_sales", "#0f172a"),
            ("مرتجعات اليوم", "returns_today", "#dc2626"),
            ("مصروفات اليوم", "expenses_today", "#d97706"),
            ("تنبيهات نواقص المخزون", "low_stock", "#d97706"),
            ("إجمالي قيمة المخزون", "inventory_value", "#16a34a"),
        ]

        for index, (title, key, color) in enumerate(cards):
            row = index // 4
            column = 3 - (index % 4)
            card = tk.Frame(self.metrics_frame, bg="white", padx=20, pady=15)
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            tk.Label(card, text=title, font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
            font_size = 18 if key == "session_status" else 22
            label = tk.Label(card, text="0.00", font=("Helvetica", font_size, "bold"), fg=color, bg="white", wraplength=180, justify="right")
            label.pack(anchor="e", pady=(5, 0))
            self.metric_labels[key] = label

    def refresh_data(self):
        summary = get_dashboard_summary()

        session_status = summary["current_session_status"]
        session_text = session_status if summary["current_session_id"] is None else f"جلسة #{summary['current_session_id']} - {session_status}"
        self.metric_labels["session_status"].config(text=session_text, fg="#16a34a" if summary["current_session_id"] else "#dc2626")
        self.metric_labels["expected_cash"].config(text=f"{summary['current_session_expected_cash']:,.2f}")
        self.metric_labels["sales_today"].config(text=f"{summary['sales_today']:,.2f}")
        self.metric_labels["net_sales"].config(text=f"{summary['net_sales_today']:,.2f}")
        self.metric_labels["returns_today"].config(text=f"{summary['returns_today']:,.2f}")
        self.metric_labels["expenses_today"].config(text=f"{summary['expenses_today']:,.2f}")
        self.metric_labels["low_stock"].config(text=f"{summary['low_stock']:,}", fg="#dc2626" if summary["low_stock"] > 0 else "#16a34a")
        self.metric_labels["inventory_value"].config(text=f"{summary['inventory_value']:,.2f}")

        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        for sale in get_recent_sales(limit=20):
            customer_name = sale["customer_name"] or "عميل عام (نقدي)"
            self.sales_tree.insert("", "end", values=(sale["id"], sale["sale_date"], customer_name, f"{sale['total_amount']:,.2f}", sale["payment_method"]))

    def _on_sale_double_click(self, event):
        selected_item = self.sales_tree.selection()
        if not selected_item:
            return

        item_values = self.sales_tree.item(selected_item[0], "values")
        sale_id, sale_date, customer, total, payment = item_values
        details = get_sale_details(sale_id)

        modal = tk.Toplevel(self)
        modal.title(f"تفاصيل الفاتورة رقم #{sale_id}")
        modal.geometry("550x500")
        modal.config(bg="white")
        modal.grab_set()

        tk.Label(modal, text=f"إيصال مبيعات - فاتورة #{sale_id}", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(20, 5))
        tk.Label(modal, text=f"التاريخ والوقت: {sale_date}", font=("Helvetica", 11), bg="white", fg="#64748b").pack()
        tk.Label(modal, text=f"العميل: {customer} | طريقة الدفع: {payment}", font=("Helvetica", 11), bg="white", fg="#64748b").pack(pady=(0, 15))

        frame_items = tk.Frame(modal, bg="white", padx=20)
        frame_items.pack(fill="both", expand=True)

        cols = ("subtotal", "price", "qty", "item")
        tree = ttk.Treeview(frame_items, columns=cols, show="headings", height=10)
        tree.heading("subtotal", text="المجموع الفرعي")
        tree.heading("price", text="سعر الوحدة")
        tree.heading("qty", text="الكمية")
        tree.heading("item", text="المنتج")
        tree.column("subtotal", width=100, anchor="center")
        tree.column("price", width=100, anchor="center")
        tree.column("qty", width=60, anchor="center")
        tree.column("item", width=240, anchor="e")
        tree.pack(fill="both", expand=True)

        for detail in details:
            tree.insert("", "end", values=(f"{detail['subtotal']:,.2f}", f"{detail['unit_price']:,.2f}", detail["quantity"], f"[{detail['sku']}] {detail['product_name']}"))

        tk.Label(modal, text=f"الإجمالي المدفوع: {total}", font=("Helvetica", 18, "bold"), bg="white", fg="#2563eb").pack(pady=15)
        tk.Button(modal, text="إغلاق الإيصال", font=("Helvetica", 12, "bold"), bg="#e2e8f0", fg="#0f172a", padx=25, pady=8, bd=0, cursor="hand2", command=modal.destroy).pack(pady=(0, 20))

        btn_add_prod = tk.Button(quick_frame, text="📦 إضافة منتج جديد", font=("Helvetica", 11, "bold"), bg="#16a34a", fg="white", 
                                 padx=15, pady=6, bd=0, cursor="hand2", command=lambda: self.controller.show_view("InventoryView"))
        btn_add_prod.pack(side="right", padx=5)

        btn_pos = tk.Button(quick_frame, text="🛒 بدء عملية بيع", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white", 
                            padx=15, pady=6, bd=0, cursor="hand2", command=lambda: self.controller.show_view("POSView"))
        btn_pos.pack(side="right", padx=5)

        # 2. Metrics Grid Frame (RTL order)
        self.metrics_frame = tk.Frame(self, bg="#f1f5f9")
        self.metrics_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.metrics_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_sales_today = None
        self.lbl_total_prods = None
        self.lbl_low_stock = None
        self.lbl_inv_val = None

        self._build_metric_cards()

        # 3. Main Content: Recent Sales Section
        sales_section = tk.Frame(self, bg="white", padx=15, pady=15)
        sales_section.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        sales_section.columnconfigure(0, weight=1)
        sales_section.rowconfigure(1, weight=1)

        # Section Header
        sec_header = tk.Frame(sales_section, bg="white")
        sec_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        lbl_sec = tk.Label(sec_header, text="أحدث العمليات والفواتير", font=("Helvetica", 18, "bold"), fg="#0f172a", bg="white")
        lbl_sec.pack(side="right")

        btn_refresh = tk.Button(sec_header, text="🔄 تحديث البيانات", font=("Helvetica", 11), bg="#e2e8f0", fg="#0f172a",
                                padx=12, pady=4, bd=0, cursor="hand2", command=self.refresh_data)
        btn_refresh.pack(side="left")

        # Treeview for Recent Sales (Arabic RTL format)
        columns = ("id", "date", "customer", "amount", "payment")
        self.sales_tree = ttk.Treeview(sales_section, columns=columns, show="headings", height=12)
        
        self.sales_tree.heading("id", text="رقم الفاتورة")
        self.sales_tree.heading("date", text="التاريخ والوقت")
        self.sales_tree.heading("customer", text="اسم العميل")
        self.sales_tree.heading("amount", text="المبلغ الإجمالي")
        self.sales_tree.heading("payment", text="طريقة الدفع")

        self.sales_tree.column("id", width=90, anchor="center")
        self.sales_tree.column("date", width=180, anchor="center")
        self.sales_tree.column("customer", width=220, anchor="e")
        self.sales_tree.column("amount", width=120, anchor="center")
        self.sales_tree.column("payment", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(sales_section, orient="vertical", command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=scrollbar.set)

        self.sales_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        self.sales_tree.bind("<Double-1>", self._on_sale_double_click)

        lbl_guide = tk.Label(sales_section, text="* انقر مرتين على أي صف في الجدول لعرض إيصال تفاصيل الفاتورة والمشتريات.", 
                             font=("Helvetica", 10, "italic"), fg="#64748b", bg="white")
        lbl_guide.grid(row=2, column=0, sticky="e", pady=(10, 0))

        self.refresh_data()

    def _build_metric_cards(self):
        # Build in RTL grid order: col 3 is leftmost, col 0 is rightmost
        # 1. Sales Today (Col 3)
        card1 = tk.Frame(self.metrics_frame, bg="white", padx=20, pady=15)
        card1.grid(row=0, column=3, sticky="nsew", padx=(0, 10))
        tk.Label(card1, text="إيرادات مبيعات اليوم", font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
        self.lbl_sales_today = tk.Label(card1, text="0.00", font=("Helvetica", 24, "bold"), fg="#2563eb", bg="white")
        self.lbl_sales_today.pack(anchor="e", pady=(5, 0))

        # 2. Total Products (Col 2)
        card2 = tk.Frame(self.metrics_frame, bg="white", padx=20, pady=15)
        card2.grid(row=0, column=2, sticky="nsew", padx=10)
        tk.Label(card2, text="إجمالي المنتجات في الكتالوج", font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
        self.lbl_total_prods = tk.Label(card2, text="0", font=("Helvetica", 24, "bold"), fg="#0f172a", bg="white")
        self.lbl_total_prods.pack(anchor="e", pady=(5, 0))

        # 3. Low Stock Warnings (Col 1)
        card3 = tk.Frame(self.metrics_frame, bg="white", padx=20, pady=15)
        card3.grid(row=0, column=1, sticky="nsew", padx=10)
        tk.Label(card3, text="تنبيهات نواقص المخزون", font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
        self.lbl_low_stock = tk.Label(card3, text="0", font=("Helvetica", 24, "bold"), fg="#d97706", bg="white")
        self.lbl_low_stock.pack(anchor="e", pady=(5, 0))

        # 4. Inventory Value (Col 0)
        card4 = tk.Frame(self.metrics_frame, bg="white", padx=20, pady=15)
        card4.grid(row=0, column=0, sticky="nsew", padx=(10, 0))
        tk.Label(card4, text="إجمالي قيمة المخزون", font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
        self.lbl_inv_val = tk.Label(card4, text="0.00", font=("Helvetica", 24, "bold"), fg="#16a34a", bg="white")
        self.lbl_inv_val.pack(anchor="e", pady=(5, 0))

    def refresh_data(self):
        summary = get_dashboard_summary()
        self.lbl_sales_today.config(text=f"{summary['sales_today']:,.2f}")
        self.lbl_total_prods.config(text=f"{summary['total_products']:,}")
        self.lbl_inv_val.config(text=f"{summary['inventory_value']:,.2f}")
        
        low_count = summary['low_stock']
        self.lbl_low_stock.config(text=f"{low_count:,}", fg="#dc2626" if low_count > 0 else "#16a34a")

        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)

        recent_sales = get_recent_sales(limit=20)
        for s in recent_sales:
            cust_name = s['customer_name'] or "عميل عام (نقدي)"
            amt_str = f"{s['total_amount']:,.2f}"
            self.sales_tree.insert("", "end", values=(s['id'], s['sale_date'], cust_name, amt_str, s['payment_method']))

    def _on_sale_double_click(self, event):
        selected_item = self.sales_tree.selection()
        if not selected_item: return
        
        item_values = self.sales_tree.item(selected_item[0], "values")
        sale_id = item_values[0]
        sale_date = item_values[1]
        customer = item_values[2]
        total = item_values[3]
        payment = item_values[4]

        details = get_sale_details(sale_id)

        modal = tk.Toplevel(self)
        modal.title(f"تفاصيل الفاتورة رقم #{sale_id}")
        modal.geometry("550x500")
        modal.config(bg="white")
        modal.grab_set()

        tk.Label(modal, text=f"إيصال مبيعات - فاتورة #{sale_id}", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(20, 5))
        tk.Label(modal, text=f"التاريخ والوقت: {sale_date}", font=("Helvetica", 11), bg="white", fg="#64748b").pack()
        tk.Label(modal, text=f"العميل: {customer} | طريقة الدفع: {payment}", font=("Helvetica", 11), bg="white", fg="#64748b").pack(pady=(0, 15))

        frame_items = tk.Frame(modal, bg="white", padx=20)
        frame_items.pack(fill="both", expand=True)

        cols = ("subtotal", "price", "qty", "item")
        tree = ttk.Treeview(frame_items, columns=cols, show="headings", height=10)
        tree.heading("subtotal", text="المجموع الفرعي")
        tree.heading("price", text="سعر الوحدة")
        tree.heading("qty", text="الكمية")
        tree.heading("item", text="المنتج")

        tree.column("subtotal", width=100, anchor="center")
        tree.column("price", width=100, anchor="center")
        tree.column("qty", width=60, anchor="center")
        tree.column("item", width=240, anchor="e")

        tree.pack(fill="both", expand=True)

        for d in details:
            tree.insert("", "end", values=(
                f"{d['subtotal']:,.2f}",
                f"{d['unit_price']:,.2f}", 
                d['quantity'], 
                f"[{d['sku']}] {d['product_name']}"
            ))

        tk.Label(modal, text=f"الإجمالي المدفوع: {total}", font=("Helvetica", 18, "bold"), bg="white", fg="#2563eb").pack(pady=15)
        
        btn_close = tk.Button(modal, text="إغلاق الإيصال", font=("Helvetica", 12, "bold"), bg="#e2e8f0", fg="#0f172a", 
                              padx=25, pady=8, bd=0, cursor="hand2", command=modal.destroy)
        btn_close.pack(pady=(0, 20))
