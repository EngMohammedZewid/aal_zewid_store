import tkinter as tk
from tkinter import ttk, messagebox
from core.db import get_all_suppliers, add_supplier, get_all_purchase_orders, get_po_items, create_purchase_order, mark_po_received, get_all_products

class SuppliersView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.suppliers_list = []
        self.pos_list = []
        self.products_list = []

        header_frame = tk.Frame(self, bg="#f1f5f9")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        tk.Label(header_frame, text="🚚 المورّدون وطلبات الشراء", font=("Helvetica", 22, "bold"), fg="#0f172a", bg="#f1f5f9").pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))

        self.tab_suppliers = tk.Frame(self.notebook, bg="white", padx=15, pady=15)
        self.tab_pos = tk.Frame(self.notebook, bg="white", padx=15, pady=15)

        self.notebook.add(self.tab_suppliers, text="  🚚 دليل المورّدين  ")
        self.notebook.add(self.tab_pos, text="  📝 أوامر الشراء (إعادة التموين)  ")

        self._build_suppliers_tab()
        self._build_pos_tab()

        self.refresh_data()

    def _build_suppliers_tab(self):
        self.tab_suppliers.columnconfigure(0, weight=1)
        self.tab_suppliers.rowconfigure(1, weight=1)

        top_bar = tk.Frame(self.tab_suppliers, bg="white")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        tk.Label(top_bar, text="الشركات والمورّدون المعتمدون", font=("Helvetica", 18, "bold"), fg="#0f172a", bg="white").pack(side="right")

        btn_add = tk.Button(top_bar, text="+ إضافة مورّد جديد", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._show_add_supplier_modal)
        btn_add.pack(side="left")

        cols = ("address", "email", "phone", "contact", "name", "id")
        self.sup_tree = ttk.Treeview(self.tab_suppliers, columns=cols, show="headings", height=15)
        self.sup_tree.heading("id", text="الرقم")
        self.sup_tree.heading("name", text="اسم الشركة")
        self.sup_tree.heading("contact", text="الشخص المسؤول")
        self.sup_tree.heading("phone", text="رقم الهاتف")
        self.sup_tree.heading("email", text="البريد الإلكتروني")
        self.sup_tree.heading("address", text="العنوان الفعلي")

        self.sup_tree.column("id", width=50, anchor="center")
        self.sup_tree.column("name", width=200, anchor="e")
        self.sup_tree.column("contact", width=150, anchor="e")
        self.sup_tree.column("phone", width=120, anchor="center")
        self.sup_tree.column("email", width=180, anchor="e")
        self.sup_tree.column("address", width=250, anchor="e")

        scrollbar = ttk.Scrollbar(self.tab_suppliers, orient="vertical", command=self.sup_tree.yview)
        self.sup_tree.configure(yscrollcommand=scrollbar.set)

        self.sup_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

    def _build_pos_tab(self):
        self.tab_pos.columnconfigure(0, weight=1)
        self.tab_pos.rowconfigure(1, weight=1)

        top_bar = tk.Frame(self.tab_pos, bg="white")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        tk.Label(top_bar, text="سجل أوامر الشراء وإعادة التموين", font=("Helvetica", 18, "bold"), fg="#0f172a", bg="white").pack(side="right")

        btn_new_po = tk.Button(top_bar, text="📦 إنشاء أمر شراء جديد", font=("Helvetica", 11, "bold"), bg="#16a34a", fg="white",
                               padx=15, pady=6, bd=0, cursor="hand2", command=self._show_create_po_modal)
        btn_new_po.pack(side="left")

        cols = ("status", "total", "supplier", "date", "id")
        self.po_tree = ttk.Treeview(self.tab_pos, columns=cols, show="headings", height=15)
        self.po_tree.heading("id", text="رقم الأمر")
        self.po_tree.heading("date", text="التاريخ والوقت")
        self.po_tree.heading("supplier", text="المورّد")
        self.po_tree.heading("total", text="التكلفة الإجمالية")
        self.po_tree.heading("status", text="حالة الطلب")

        self.po_tree.column("id", width=80, anchor="center")
        self.po_tree.column("date", width=180, anchor="center")
        self.po_tree.column("supplier", width=250, anchor="e")
        self.po_tree.column("total", width=120, anchor="center")
        self.po_tree.column("status", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(self.tab_pos, orient="vertical", command=self.po_tree.yview)
        self.po_tree.configure(yscrollcommand=scrollbar.set)

        self.po_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        bot_bar = tk.Frame(self.tab_pos, bg="white")
        bot_bar.grid(row=2, column=0, sticky="ew", pady=(15, 0))

        btn_recv = tk.Button(bot_bar, text="📥 تسجيل كـ 'تم الاستلام' (إضافة للمخزون)", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white",
                             padx=15, pady=6, bd=0, cursor="hand2", command=self._receive_selected_po)
        btn_recv.pack(side="left", padx=5)

        btn_view = tk.Button(bot_bar, text="🔍 عرض تفاصيل أمر الشراء", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a",
                             padx=15, pady=6, bd=0, cursor="hand2", command=self._view_po_details)
        btn_view.pack(side="left", padx=5)

    def refresh_data(self):
        self.suppliers_list = get_all_suppliers()
        for item in self.sup_tree.get_children():
            self.sup_tree.delete(item)
        for s in self.suppliers_list:
            self.sup_tree.insert("", "end", values=(s['address'] or "N/A", s['email'] or "N/A", s['phone'] or "N/A", s['contact_person'] or "N/A", s['name'], s['id']))

        self.pos_list = get_all_purchase_orders()
        for item in self.po_tree.get_children():
            self.po_tree.delete(item)
        for po in self.pos_list:
            tot_str = f"${po['total_cost']:,.2f}"
            status = po['status']
            tag = "received" if status == "تم الاستلام" else "pending"
            self.po_tree.insert("", "end", values=(status, tot_str, po['supplier_name'], po['po_date'], po['id']), tags=(tag,))

        self.po_tree.tag_configure("received", foreground="#16a34a", font=("Helvetica", 11, "bold"))
        self.po_tree.tag_configure("pending", foreground="#d97706", font=("Helvetica", 11, "bold"))

        self.products_list = get_all_products()

    def _show_add_supplier_modal(self):
        modal = tk.Toplevel(self)
        modal.title("إضافة مورّد جديد")
        modal.geometry("450x480")
        modal.config(bg="white", padx=25, pady=25)
        modal.grab_set()

        modal.columnconfigure(0, weight=1)

        tk.Label(modal, text="إضافة مورّد جديد", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 20))

        form = tk.Frame(modal, bg="white")
        form.pack(fill="both", expand=True)
        form.columnconfigure(0, weight=1)

        fields = [
            ("اسم الشركة المورّدة *", "name"),
            ("الشخص المسؤول", "contact"),
            ("رقم الهاتف *", "phone"),
            ("البريد الإلكتروني", "email"),
            ("العنوان الكامل", "address")
        ]

        entries = {}
        for i, (lbl, fname) in enumerate(fields):
            tk.Label(form, text=lbl, font=("Helvetica", 11, "bold"), bg="white", fg="#334155").grid(row=i, column=1, sticky="e", pady=10, padx=10)
            ent = tk.Entry(form, font=("Helvetica", 12), width=24, justify="right")
            ent.grid(row=i, column=0, pady=10, padx=5)
            entries[fname] = ent

        def save_sup():
            name = entries['name'].get().strip()
            contact = entries['contact'].get().strip()
            phone = entries['phone'].get().strip()
            email = entries['email'].get().strip()
            addr = entries['address'].get().strip()

            if not name or not phone:
                messagebox.showwarning("بيانات مطلوبة", "اسم الشركة ورقم الهاتف مطلوبان.")
                return

            s, m = add_supplier(name, contact, phone, email, addr)
            if s:
                messagebox.showinfo("نجاح", m)
                self.refresh_data()
                modal.destroy()
            else:
                messagebox.showerror("خطأ", m)

        btn_save = tk.Button(modal, text="💾 حفظ بيانات المورّد", font=("Helvetica", 13, "bold"), bg="#2563eb", fg="white",
                             pady=10, bd=0, cursor="hand2", command=save_sup)
        btn_save.pack(fill="x", pady=(20, 0))

    def _show_create_po_modal(self):
        if not self.suppliers_list:
            messagebox.showwarning("لا يوجد مورّدون", "يرجى تسجيل مورّد واحد على الأقل قبل إنشاء أمر شراء.")
            return

        modal = tk.Toplevel(self)
        modal.title("إنشاء أمر شراء جديد")
        modal.geometry("750x600")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        modal.columnconfigure(0, weight=1)
        modal.rowconfigure(2, weight=1)

        sup_frame = tk.Frame(modal, bg="white")
        sup_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        tk.Label(sup_frame, text="اختر المورّد:", font=("Helvetica", 12, "bold"), bg="white", fg="#0f172a").pack(side="right", padx=(10, 0))
        cb_sup = ttk.Combobox(sup_frame, state="readonly", font=("Helvetica", 12), width=35, justify="right")
        sup_names = [f"{s['name']} ({s['contact_person'] or 'بدون مسؤول'})" for s in self.suppliers_list]
        cb_sup.config(values=sup_names)
        cb_sup.set(sup_names[0])
        cb_sup.pack(side="right", padx=10)

        item_bar = tk.Frame(modal, bg="#f8fafc", padx=10, pady=10, bd=1, relief="solid")
        item_bar.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        tk.Label(item_bar, text="المنتج:", font=("Helvetica", 11, "bold"), bg="#f8fafc").pack(side="right", padx=5)
        cb_prod = ttk.Combobox(item_bar, state="readonly", font=("Helvetica", 11), width=28, justify="right")
        prod_names = [f"[{p['sku']}] {p['name']}" for p in self.products_list]
        cb_prod.config(values=prod_names)
        if prod_names: cb_prod.set(prod_names[0])
        cb_prod.pack(side="right", padx=5)

        tk.Label(item_bar, text="الكمية:", font=("Helvetica", 11, "bold"), bg="#f8fafc").pack(side="right", padx=5)
        ent_qty = tk.Entry(item_bar, font=("Helvetica", 11), width=6, justify="center")
        ent_qty.insert(0, "10")
        ent_qty.pack(side="right", padx=5)

        tk.Label(item_bar, text="سعر الوحدة ($):", font=("Helvetica", 11, "bold"), bg="#f8fafc").pack(side="right", padx=5)
        ent_cost = tk.Entry(item_bar, font=("Helvetica", 11), width=8, justify="center")
        ent_cost.insert(0, "0.00")
        ent_cost.pack(side="right", padx=5)

        po_items_list = [] 

        def on_prod_change(event):
            idx = cb_prod.current()
            if idx >= 0:
                p = self.products_list[idx]
                ent_cost.delete(0, "end")
                ent_cost.insert(0, f"{p['cost_price']:.2f}")

        cb_prod.bind("<<ComboboxSelected>>", on_prod_change)
        if self.products_list: on_prod_change(None)

        tree_frame = tk.Frame(modal, bg="white")
        tree_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 15))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        cols = ("sub", "cost", "qty", "name", "sku")
        po_item_tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        po_item_tree.heading("sku", text="كود المنتج")
        po_item_tree.heading("name", text="اسم المنتج")
        po_item_tree.heading("qty", text="الكمية")
        po_item_tree.heading("cost", text="سعر الوحدة")
        po_item_tree.heading("sub", text="المجموع")

        po_item_tree.column("sku", width=90, anchor="center")
        po_item_tree.column("name", width=220, anchor="e")
        po_item_tree.column("qty", width=80, anchor="center")
        po_item_tree.column("cost", width=100, anchor="center")
        po_item_tree.column("sub", width=100, anchor="center")

        po_item_tree.grid(row=0, column=0, sticky="nsew")

        lbl_tot = tk.Label(modal, text="الإجمالي الكلي: $0.00", font=("Helvetica", 18, "bold"), fg="#2563eb", bg="white")
        lbl_tot.grid(row=3, column=0, sticky="w", pady=(0, 15))

        def update_po_tot():
            for item in po_item_tree.get_children():
                po_item_tree.delete(item)

            tot = 0.0
            for p, q, c in po_items_list:
                sub = q * c
                tot += sub
                po_item_tree.insert("", "end", values=(f"${sub:,.2f}", f"${c:,.2f}", q, p['name'], p['sku']))

            lbl_tot.config(text=f"الإجمالي الكلي: ${tot:,.2f}")

        def add_to_po():
            idx = cb_prod.current()
            if idx < 0: return
            p = self.products_list[idx]

            try:
                q = int(ent_qty.get())
                c = float(ent_cost.get())
                if q <= 0 or c < 0: raise ValueError
            except ValueError:
                messagebox.showerror("إدخال غير صحيح", "يرجى إدخال أرقام صحيحة للكمية وسعر الوحدة.")
                return

            po_items_list.append((p, q, c))
            update_po_tot()

        btn_add_item = tk.Button(item_bar, text="➕ إضافة للأمر", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white",
                                 padx=12, pady=4, bd=0, cursor="hand2", command=add_to_po)
        btn_add_item.pack(side="left")

        def confirm_po():
            if not po_items_list:
                messagebox.showwarning("أمر فارغ", "يرجى إضافة منتج واحد على الأقل إلى أمر الشراء.")
                return

            sup_idx = cb_sup.current()
            sup_id = self.suppliers_list[sup_idx]['id']

            items_data = [(p['id'], q, c) for p, q, c in po_items_list]
            tot_cost = sum(q * c for p, q, c in po_items_list)

            s, m = create_purchase_order(sup_id, items_data, tot_cost)
            if s:
                messagebox.showinfo("نجاح", m)
                self.refresh_data()
                modal.destroy()
            else:
                messagebox.showerror("خطأ", m)

        btn_confirm = tk.Button(modal, text="💾 إرسال واعتماد أمر الشراء", font=("Helvetica", 15, "bold"), bg="#16a34a", fg="white",
                                pady=12, bd=0, cursor="hand2", command=confirm_po)
        btn_confirm.grid(row=4, column=0, sticky="ew")

    def _view_po_details(self):
        selected = self.po_tree.selection()
        if not selected:
            messagebox.showinfo("تحديد أمر شراء", "يرجى تحديد أمر شراء من الجدول لعرض تفاصيله.")
            return

        values = self.po_tree.item(selected[0], "values")
        status = values[0]
        tot = values[1]
        supplier = values[2]
        po_date = values[3]
        po_id = int(values[4])

        items = get_po_items(po_id)

        modal = tk.Toplevel(self)
        modal.title(f"تفاصيل أمر الشراء رقم #{po_id}")
        modal.geometry("600x480")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text=f"أمر شراء رقم #{po_id}", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 5))
        tk.Label(modal, text=f"المورّد: {supplier} | التاريخ: {po_date}", font=("Helvetica", 11), bg="white", fg="#64748b").pack()
        tk.Label(modal, text=f"الحالة: {status}", font=("Helvetica", 12, "bold"), bg="white", fg="#16a34a" if status=="تم الاستلام" else "#d97706").pack(pady=(0, 15))

        cols = ("sub", "cost", "qty", "name", "sku")
        tree = ttk.Treeview(modal, columns=cols, show="headings")
        tree.heading("sku", text="كود المنتج")
        tree.heading("name", text="اسم المنتج")
        tree.heading("qty", text="الكمية")
        tree.heading("cost", text="سعر الوحدة")
        tree.heading("sub", text="المجموع")

        tree.column("sku", width=90, anchor="center")
        tree.column("name", width=220, anchor="e")
        tree.column("qty", width=60, anchor="center")
        tree.column("cost", width=100, anchor="center")
        tree.column("sub", width=100, anchor="center")

        tree.pack(fill="both", expand=True, pady=(0, 15))

        for item in items:
            tree.insert("", "end", values=(f"${item['quantity']*item['unit_cost']:,.2f}", f"${item['unit_cost']:,.2f}", item['quantity'], item['product_name'], item['sku']))

        tk.Label(modal, text=f"التكلفة الإجمالية: {tot}", font=("Helvetica", 16, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 10))

        btn_close = tk.Button(modal, text="إغلاق", font=("Helvetica", 12, "bold"), bg="#e2e8f0", fg="#0f172a",
                              padx=30, pady=8, bd=0, cursor="hand2", command=modal.destroy)
        btn_close.pack(pady=(5, 0))

    def _receive_selected_po(self):
        selected = self.po_tree.selection()
        if not selected:
            messagebox.showinfo("تحديد أمر شراء", "يرجى تحديد أمر شراء قيد الانتظار لتسجيله كـ 'تم الاستلام'.")
            return

        values = self.po_tree.item(selected[0], "values")
        status = values[0]
        po_id = int(values[4])

        if status == "تم الاستلام":
            messagebox.showinfo("مستلم مسبقاً", f"أمر الشراء رقم #{po_id} مسجل كـ 'تم الاستلام' وتمت إضافة كمياته إلى المخزون مسبقاً.")
            return

        if messagebox.askyesno("تأكيد الاستلام", f"هل تريد تسجيل أمر الشراء رقم #{po_id} كـ 'تم الاستلام'؟\nهذا الإجراء سيقوم تلقائياً بإضافة جميع كميات المنتجات المطلوبة في هذا الأمر إلى مخزون المتجر الفعلي."):
            s, m = mark_po_received(po_id)
            if s:
                messagebox.showinfo("تم الاستلام وإضافة المخزون!", m)
                self.refresh_data()
                self.controller.refresh_all_views()
            else:
                messagebox.showerror("خطأ", m)
