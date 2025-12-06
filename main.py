import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk, Menu
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, UnidentifiedImageError
import os
import io
import datetime
import re
import subprocess
import platform
import pillow_avif
import pillow_heif

pillow_heif.register_heif_opener()

ctk.set_appearance_mode("Dark")
ME_YELLOW = "#FFCC00"
ME_YELLOW_HOVER = "#E6B800"
ME_BLACK = "#2D2D2D"
ME_TEXT_ON_YELLOW = "black"

class AsystentApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Asystent PIM Media Expert v1.0.0")
        self.geometry("1350x900") # Trochę wyższe okno dla suwaka
        self.set_icon()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.file_list = []
        self.overwrite_var = ctk.BooleanVar(value=True)
        self.current_preview_path = None
        self.preview_image_ref = None 
        self.setup_ui()

    def set_icon(self):
        try:
            icon_size = 64
            icon_img = Image.new("RGB", (icon_size, icon_size), color=ME_YELLOW)
            draw = ImageDraw.Draw(icon_img)
            draw.rectangle([0, 0, icon_size-1, icon_size-1], outline="black", width=4)
            self.icon_image = tk.PhotoImage(data=self.image_to_data(icon_img))
            self.wm_iconphoto(True, self.icon_image)
        except Exception: pass

    def image_to_data(self, im):
        from io import BytesIO
        with BytesIO() as output:
            im.save(output, format="PNG")
            return output.getvalue()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=ME_BLACK)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(25, weight=1) # Więcej miejsca na dole

        ctk.CTkLabel(self.sidebar, text="Asystent PIM", font=ctk.CTkFont(size=24, weight="bold"), text_color=ME_YELLOW).grid(row=0, column=0, padx=20, pady=(20, 10))
        ctk.CTkLabel(self.sidebar, text="MEDIA EXPERT", font=ctk.CTkFont(size=12, weight="bold"), text_color="white").grid(row=1, column=0, padx=20, pady=(0, 20))

        btn_me = {"width": 200, "height": 40, "corner_radius": 4, "fg_color": ME_YELLOW, "text_color": ME_TEXT_ON_YELLOW, "hover_color": ME_YELLOW_HOVER, "font": ctk.CTkFont(weight="bold")}
        
        ctk.CTkButton(self.sidebar, text="DODAJ OBRAZY", command=self.add_images, **btn_me).grid(row=2, column=0, padx=15, pady=8)
        ctk.CTkButton(self.sidebar, text="WYCZYŚĆ LISTĘ", command=self.clear_list, fg_color="#444444", text_color="white", hover_color="#666666", width=200, height=35).grid(row=3, column=0, padx=15, pady=5)
        ctk.CTkButton(self.sidebar, text="USUŃ ZAZNACZONY", command=self.remove_selected, fg_color="transparent", border_width=1, border_color="gray50", text_color="gray80", width=200).grid(row=4, column=0, padx=15, pady=5)

        # KOLEJNOŚĆ
        ctk.CTkLabel(self.sidebar, text="KOLEJNOŚĆ", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").grid(row=5, column=0, padx=20, pady=(15,5))
        move_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        move_frame.grid(row=6, column=0)
        ctk.CTkButton(move_frame, text="▲", command=self.move_up, width=95, height=30, fg_color="#444444", hover_color="#666666").pack(side="left", padx=5)
        ctk.CTkButton(move_frame, text="▼", command=self.move_down, width=95, height=30, fg_color="#444444", hover_color="#666666").pack(side="left", padx=5)

        # EDYCJA I SUWAK
        ctk.CTkLabel(self.sidebar, text="USTAWIENIA JPG", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").grid(row=7, column=0, padx=20, pady=(15,5))
        
        # Suwak Jakości
        self.lbl_quality = ctk.CTkLabel(self.sidebar, text="Jakość: 95", text_color="white")
        self.lbl_quality.grid(row=8, column=0, padx=20, pady=0)
        
        self.slider_quality = ctk.CTkSlider(self.sidebar, from_=10, to=100, number_of_steps=90, command=self.update_quality_label, width=180, progress_color=ME_YELLOW, button_color="white", button_hover_color=ME_YELLOW)
        self.slider_quality.set(95)
        self.slider_quality.grid(row=9, column=0, padx=20, pady=5)

        self.chk_overwrite = ctk.CTkCheckBox(self.sidebar, text="Nadpisz pliki", variable=self.overwrite_var, font=ctk.CTkFont(size=12), text_color="white", fg_color=ME_YELLOW, hover_color=ME_YELLOW_HOVER, checkmark_color="black")
        self.chk_overwrite.grid(row=10, column=0, padx=25, pady=10, sticky="w")

        # OPERACJE
        ctk.CTkLabel(self.sidebar, text="OPERACJE", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").grid(row=11, column=0, padx=20, pady=(10,5))

        ops = [
            ("KONWERTUJ DO JPG", self.convert_to_jpg),
            ("DODAJ BIAŁE TŁO", self.add_white_bg),
            ("DODAJ RAMKĘ 5px", self.add_border_5px),
            ("KADRUJ", self.auto_crop),
            ("ZWIĘKSZ DO 500px", self.upscale_500),
            ("DOPASUJ DO 3000px", self.downscale_3000),
            ("KOMPRESUJ DO 3 MB", self.smart_compress_3mb) # Nowy przycisk
        ]

        r = 12
        for text, cmd in ops:
            ctk.CTkButton(self.sidebar, text=text, command=cmd, **btn_me).grid(row=r, column=0, padx=15, pady=5)
            r += 1

        # --- PANEL GŁÓWNY ---
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_area.grid_rowconfigure(2, weight=1)
        self.main_area.grid_columnconfigure(0, weight=3)
        self.main_area.grid_columnconfigure(1, weight=1)

        self.top_frame = ctk.CTkFrame(self.main_area, corner_radius=0, fg_color="#222222")
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(self.top_frame, text="Nazwa Produktu:", font=ctk.CTkFont(weight="bold"), text_color="white").pack(side="left", padx=20, pady=15)
        self.entry_name = ctk.CTkEntry(self.top_frame, width=400, placeholder_text="Wpisz nazwę produktu...", border_color=ME_YELLOW)
        self.entry_name.pack(side="left", padx=5, pady=15)
        ctk.CTkButton(self.top_frame, text="WKLEJ", command=self.paste_from_clipboard, width=60, fg_color="#444444", hover_color="#666666").pack(side="left", padx=5)
        ctk.CTkButton(self.top_frame, text="ZASTOSUJ I ZMIEŃ NAZWY", command=self.rename_files, fg_color="#2CC937", text_color="black", width=220, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=20, pady=15)

        self.list_frame = ctk.CTkFrame(self.main_area, corner_radius=10, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=15)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.list_frame, text="Lista plików", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=0, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=30, fieldbackground="#2b2b2b", borderwidth=0, font=("Segoe UI", 10))
        style.map('Treeview', background=[('selected', ME_YELLOW)], foreground=[('selected', 'black')])
        style.configure("Treeview.Heading", background="#333333", foreground="white", relief="flat", font=("Segoe UI", 10, "bold"))
        
        self.tree = ttk.Treeview(self.list_frame, columns=("lp", "nazwa", "rozmiar", "wymiar", "akcja"), show="headings", selectmode="extended")
        self.tree.heading("lp", text="Lp.", anchor="center")
        self.tree.heading("nazwa", text="Nazwa pliku", anchor="w")
        self.tree.heading("rozmiar", text="Rozmiar", anchor="center")
        self.tree.heading("wymiar", text="Wymiar", anchor="center")
        self.tree.heading("akcja", text="Folder", anchor="center")
        self.tree.column("lp", width=50, anchor="center")
        self.tree.column("nazwa", width=400)
        self.tree.column("rozmiar", width=100)
        self.tree.column("wymiar", width=120)
        self.tree.column("akcja", width=60, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        
        scrollbar = ctk.CTkScrollbar(self.list_frame, command=self.tree.yview, fg_color="transparent", button_color="#444444", button_hover_color="#666666")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self.context_menu = Menu(self.main_area, tearoff=0, bg="#2D2D2D", fg="white", activebackground=ME_YELLOW, activeforeground="black")
        self.context_menu.add_command(label="Otwórz plik", command=self.open_file_default)
        self.context_menu.add_command(label="Otwórz folder pliku", command=self.open_folder_context)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Usuń z listy", command=self.remove_selected)

        self.preview_frame = ctk.CTkFrame(self.main_area, corner_radius=10, fg_color="#222222")
        self.preview_frame.grid(row=2, column=1, sticky="nsew", padx=15, pady=15)
        self.preview_frame.grid_propagate(False)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=0)
        self.preview_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.preview_frame, text="Podgląd", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, pady=10)
        self.lbl_preview = tk.Label(self.preview_frame, text="Wybierz plik", fg="gray", bg="#222222", font=("Segoe UI", 10))
        self.lbl_preview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        self.status_label = ctk.CTkLabel(self.main_area, text="Gotowy", anchor="w", text_color="gray")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5,10), padx=20)

    def update_quality_label(self, value):
        self.lbl_quality.configure(text=f"Jakość: {int(value)}")

    def paste_from_clipboard(self):
        try:
            text = self.sidebar.clipboard_get()
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, text)
        except: pass

    def clean_filename(self, text):
        replacements = {'ą':'a','ć':'c','ę':'e','ł':'l','ń':'n','ó':'o','ś':'s','ź':'z','ż':'z','Ą':'A','Ć':'C','Ę':'E','Ł':'L','Ń':'N','Ó':'O','Ś':'S','Ź':'Z','Ż':'Z'}
        for k, v in replacements.items(): text = text.replace(k, v)
        text = text.replace(" ", "-")
        text = re.sub(r'[^a-zA-Z0-9\.-]', '-', text)
        text = re.sub(r'-+', '-', text)
        return text.strip('-')

    def update_indexes(self):
        new_list = []
        to_remove = []
        for index, item in enumerate(self.tree.get_children()):
            path = self.tree.item(item)['tags'][0]
            if os.path.exists(path):
                self.tree.set(item, "lp", str(index + 1))
                new_list.append(path)
            else:
                to_remove.append(item)
        for item in to_remove: self.tree.delete(item)
        self.file_list = new_list

    def move_up(self):
        selected = self.tree.selection()
        if not selected: return
        for item in selected:
            idx = self.tree.index(item)
            if idx > 0: self.tree.move(item, self.tree.parent(item), idx - 1)
        self.update_indexes()

    def move_down(self):
        selected = self.tree.selection()
        if not selected: return
        for item in reversed(selected):
            idx = self.tree.index(item)
            last = len(self.tree.get_children()) - 1
            if idx < last: self.tree.move(item, self.tree.parent(item), idx + 1)
        self.update_indexes()

    def rename_files(self):
        base = self.entry_name.get()
        if not base: return messagebox.showwarning("Błąd", "Wpisz nazwę produktu!")
        clean_base = self.clean_filename(base)
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, clean_base)
        items = self.tree.get_children()
        if not items: return
        count = 1
        renamed = 0
        for item in items:
            old_path = self.tree.item(item)['tags'][0]
            if not os.path.exists(old_path): continue
            folder = os.path.dirname(old_path)
            ext = os.path.splitext(old_path)[1]
            new_filename = f"{clean_base}-{count}{ext}"
            new_path = os.path.join(folder, new_filename)
            if old_path != new_path:
                try:
                    os.rename(old_path, new_path)
                    size = os.path.getsize(new_path)
                    name = os.path.basename(new_path)
                    dim = self.tree.item(item)['values'][3]
                    self.tree.item(item, values=(count, name, self.format_bytes(size), dim, "📂"), tags=[new_path])
                    renamed += 1
                except Exception as e: print(f"Rename err: {e}")
            else:
                self.tree.set(item, "lp", str(count))
            count += 1
        self.update_indexes()
        self.status_label.configure(text=f"Zmieniono nazwy dla {renamed} plików.")

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            row_id = self.tree.identify_row(event.y)
            if not row_id: return
            file_path = self.tree.item(row_id)['tags'][0]
            if column == "#5": self.open_file_location(file_path)
            else: self.show_preview(file_path)

    def show_context_menu(self, event):
        try:
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
                self.context_menu.post(event.x_root, event.y_root)
        except: pass

    def open_file_default(self):
        sel = self.tree.selection()
        if sel: self.open_path(self.tree.item(sel[0])['tags'][0])

    def open_folder_context(self):
        sel = self.tree.selection()
        if sel: self.open_file_location(self.tree.item(sel[0])['tags'][0])

    def open_path(self, path):
        if not os.path.exists(path): return
        try:
            if platform.system() == 'Windows': os.startfile(path)
            elif platform.system() == 'Darwin': subprocess.Popen(['open', path])
            else: subprocess.Popen(['xdg-open', path])
        except: pass

    def open_file_location(self, path):
        if not os.path.exists(path): 
            self.status_label.configure(text="Błąd: Plik nie istnieje.")
            self.update_indexes()
            return
        folder = os.path.dirname(path)
        try:
            if platform.system() == "Windows": subprocess.Popen(f'explorer /select,"{path}"')
            elif platform.system() == "Darwin": subprocess.Popen(["open", "-R", path])
            else: subprocess.Popen(["xdg-open", folder])
        except Exception as e: print(f"Open folder err: {e}")

    def show_preview(self, file_path):
        try:
            if not os.path.exists(file_path):
                self.lbl_preview.configure(text="Plik nie istnieje", image="")
                self.update_indexes()
                return
            self.lbl_preview.configure(image="", text="Ładowanie...")
            self.update_idletasks()
            pil_image = Image.open(file_path)
            w, h = pil_image.size
            max_s = 400
            r = min(max_s/w, max_s/h)
            new_w = int(w * r)
            new_h = int(h * r)
            resized = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            tk_image = ImageTk.PhotoImage(resized)
            self.preview_image_ref = tk_image
            self.lbl_preview.configure(image=tk_image, text="")
            self.current_preview_path = file_path
        except Exception as e:
            self.lbl_preview.configure(image="", text="Błąd wyświetlania")

    def add_images(self):
        types = [("Obrazy", "*.jpg *.jpeg *.png *.bmp *.webp *.heic *.avif *.tiff *.JPG *.JPEG *.PNG *.BMP *.WEBP *.HEIC *.AVIF *.TIFF")]
        files = filedialog.askopenfilenames(filetypes=types)
        if files:
            for path in files:
                exists = False
                for e in self.file_list:
                    if e == path: exists = True
                if not exists:
                    self.file_list.append(path)
                    self.insert_tree_item(path)
            self.update_indexes()

    def insert_tree_item(self, path):
        if not os.path.exists(path): return
        try:
            size = os.path.getsize(path)
            name = os.path.basename(path)
            res = "N/A"
            try:
                with Image.open(path) as img: res = f"{img.width}x{img.height} px"
            except: pass
            self.tree.insert("", "end", values=("", name, self.format_bytes(size), res, "📂"), tags=[path])
        except: pass

    def remove_selected(self):
        for item in self.tree.selection(): self.tree.delete(item)
        self.update_indexes()
        self.lbl_preview.configure(image="", text="Wybierz plik")

    def clear_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.file_list.clear()
        self.lbl_preview.configure(image="", text="Wybierz plik")

    def format_bytes(self, s):
        p = 2**10
        n = 0
        l = {0:'', 1:'KB', 2:'MB', 3:'GB'}
        while s > p:
            s /= p
            n += 1
        return f"{s:.2f} {l.get(n, '')}"

    def process_images(self, name, func):
        selected = self.tree.selection()
        if not selected: return messagebox.showwarning("Info", "Wybierz pliki.")
        
        overwrite = self.overwrite_var.get()
        self.status_label.configure(text=f"Przetwarzanie: {name}...")
        self.update_idletasks()

        # Pobieramy jakość z suwaka dla operacji JPG
        quality_val = int(self.slider_quality.get())

        for item in selected:
            path = self.tree.item(item)['tags'][0]
            if not os.path.exists(path): continue

            try:
                with Image.open(path) as img:
                    img.load()
                    res = func(img) # Wywołanie funkcji transformującej
                    if res:
                        original_dir = os.path.dirname(path)
                        save_path = path 

                        if not overwrite:
                            orig_archive_dir = os.path.join(original_dir, "_orig")
                            os.makedirs(orig_archive_dir, exist_ok=True)
                            original_filename = os.path.basename(path)
                            archived_original_path = os.path.join(orig_archive_dir, original_filename)
                            try:
                                os.rename(path, archived_original_path)
                                n, e = os.path.splitext(path)
                                suffix = name.lower().replace(' ','')
                                # Przy "konwertuj do jpg", suffix nie jest potrzebny w nazwie jeśli zmieniamy rozszerzenie
                                if name == "JPG":
                                    save_path = f"{n}.jpg"
                                else:
                                    save_path = f"{n}_{suffix}{e}"
                            except Exception as e:
                                print(f"Archive err: {e}")
                                continue
                        
                        # FIX DLA JPG / ZAPIS
                        if name == "JPG" or (overwrite and name == "Kompresja3MB"):
                             # Jeśli kompresja, to nazwa może zostać, ale format musi być JPG
                             pass

                        # Logika zapisu
                        if name == "JPG":
                            if res.mode != 'RGB': res = res.convert('RGB')
                            root, _ = os.path.splitext(save_path)
                            save_path = root + ".jpg"
                            res.save(save_path, quality=quality_val, optimize=True, progressive=True)
                        
                        elif name == "Kompresja3MB":
                            # Logika specjalna dla kompresji
                            if res.mode != 'RGB': res = res.convert('RGB')
                            root, _ = os.path.splitext(save_path)
                            save_path = root + ".jpg"
                            self.save_compressed_limit(res, save_path, 3 * 1024 * 1024)
                        
                        else:
                            # Inne operacje (kadrowanie itp)
                            if save_path.lower().endswith(('.jpg', '.jpeg')):
                                if res.mode != 'RGB': res = res.convert('RGB')
                                res.save(save_path, quality=quality_val, optimize=True, progressive=True)
                            else:
                                res.save(save_path)

                        # Aktualizacja UI
                        if os.path.exists(save_path):
                            # Jeśli przenieśliśmy oryginał, musimy zaktualizować listę żeby wskazywała na nowy plik
                            if not overwrite:
                                self.file_list.remove(path)
                                self.file_list.append(save_path)
                            
                            size = os.path.getsize(save_path)
                            dim = f"{res.width}x{res.height} px"
                            vals = self.tree.item(item)['values']
                            self.tree.item(item, values=(vals[0], os.path.basename(save_path), self.format_bytes(size), dim, "📂"), tags=[save_path])
                            
                            if self.current_preview_path == path:
                                self.show_preview(save_path)

            except Exception as e:
                print(f"Err {name}: {e}")
                self.status_label.configure(text=f"Błąd: {os.path.basename(path)}")

        self.update_indexes()
        self.status_label.configure(text=f"Zakończono: {name}")

    def save_compressed_limit(self, img, path, limit_bytes):
        # Algorytm kompresji do rozmiaru
        quality = 95
        min_quality = 65
        
        # Najpierw spróbuj samą jakością
        while quality >= min_quality:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            size = buffer.getbuffer().nbytes
            if size <= limit_bytes:
                with open(path, "wb") as f:
                    f.write(buffer.getbuffer())
                return
            quality -= 5
        
        # Jeśli nadal za duży, zmniejszamy rozdzielczość
        scale = 0.9
        while True:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            if new_w < 100 or new_h < 100: break # Bezpiecznik
            
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=min_quality, optimize=True, progressive=True)
            
            if buffer.getbuffer().nbytes <= limit_bytes:
                with open(path, "wb") as f:
                    f.write(buffer.getbuffer())
                return
            scale *= 0.9 # Zmniejszaj o kolejne 10%

    def convert_to_jpg(self): self.process_images("JPG", lambda i: i.convert("RGB"))
    
    def smart_compress_3mb(self):
        # Funkcja tożsamościowa, bo cała logika jest w process_images -> save_compressed_limit
        self.process_images("Kompresja3MB", lambda i: i)

    def add_white_bg(self):
        def f(i):
            if i.mode != 'RGBA': i = i.convert('RGBA')
            w, h = i.size
            t = max(w, h, 500)
            bg = Image.new("RGBA", (t, t), "white")
            bg.paste(i, ((t-w)//2, (t-h)//2), i)
            return bg
        self.process_images("BialeTlo", f)

    def add_border_5px(self):
        def f(i):
            if i.mode != 'RGBA': i = i.convert('RGBA')
            w, h = i.size
            nw, nh = w+10, h+10
            bg = Image.new("RGB", (nw, nh), "white")
            mask = i.split()[3] if 'A' in i.getbands() else None
            bg.paste(i, (5, 5), mask)
            return bg
        self.process_images("Ramka5px", f)

    def auto_crop(self):
        def f(i):
            if i.mode != 'RGB': i = i.convert('RGB')
            bw = i.convert("L").point(lambda x: 0 if x >= 240 else 255, '1')
            bbox = bw.getbbox()
            return i.crop(bbox) if bbox else i
        self.process_images("Kadrowanie", f)

    def upscale_500(self):
        def f(i):
            w, h = i.size
            if w < 500 or h < 500:
                r = max(500/w, 500/h)
                return i.resize((int(w*r), int(h*r)), Image.Resampling.LANCZOS)
            return i
        self.process_images("Upscale", f)

    def downscale_3000(self):
        def f(i):
            w, h = i.size
            if w > 3000 or h > 3000:
                i.thumbnail((3000, 3000), Image.Resampling.LANCZOS)
                return i
            return i
        self.process_images("Downscale", f)

if __name__ == "__main__":
    app = AsystentApp()
    app.mainloop()
