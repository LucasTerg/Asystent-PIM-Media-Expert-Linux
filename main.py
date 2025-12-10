import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk, Menu
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, UnidentifiedImageError
import os
import sys
import datetime
import re
import subprocess
import platform
import pillow_avif
import pillow_heif
import shutil
import shlex 
import io
import zipfile
import webbrowser

# Wyłącz limit pikseli dla dużych obrazów z AI
Image.MAX_IMAGE_PIXELS = None

pillow_heif.register_heif_opener()

ctk.set_appearance_mode("Dark")
ME_YELLOW = "#FFCC00"
ME_YELLOW_HOVER = "#E6B800"
ME_BLACK = "#2D2D2D"
ME_TEXT_ON_YELLOW = "black"

class AsystentApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Asystent PIM Media Expert v1.0.5") # Zmieniono na v1.0.5
        self.geometry("1350x895")
        self.set_icon()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.file_list = []
        
        # Zmieniono domyślną wartość na False
        self.overwrite_var = ctk.BooleanVar(value=False) 
        
        self.current_preview_path = None
        self.preview_image_ref = None 
        
        # Słownik do przechowywania zmiennych widoczności menu
        self.view_vars = {}
        # Słownik do przechowywania referencji do widgetów w sidebarze
        self.sidebar_widgets = {}
        
        self.bind("<Button-1>", self.hide_context_menu)
        self.setup_ui()
        self.create_main_menu()

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

    def check_ai_tools(self):
        # Określanie nazwy pliku binarnego w zależności od systemu
        system_platform = platform.system()
        if system_platform == "Windows":
            bin_name = "realesrgan-ncnn-vulkan.exe"
        elif system_platform == "Darwin": # macOS
            bin_name = "realesrgan-ncnn-vulkan-mac"
        else: # Linux
            bin_name = "realesrgan-ncnn-vulkan"

        # 1. Sprawdź czy binary istnieje w systemie (PATH)
        self.ai_tool_path = shutil.which(bin_name)
        if self.ai_tool_path: return True
        
        # 2. Sprawdź obok pliku skryptu (dla repozytorium/struktury folderów)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_bin = os.path.join(script_dir, bin_name)
        if os.path.exists(script_bin) and os.access(script_bin, os.X_OK):
            self.ai_tool_path = script_bin
            return True

        # 3. Sprawdź w bieżącym katalogu roboczym
        local_bin = os.path.abspath(bin_name)
        if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
            self.ai_tool_path = local_bin
            return True

        # 4. Sprawdź w katalogu tymczasowym PyInstallera (dla OneFile)
        if hasattr(sys, '_MEIPASS'):
            temp_bin = os.path.join(sys._MEIPASS, bin_name)
            # Na macOS wewnątrz .app binarka może nie mieć atrybutu executable po rozpakowaniu
            if os.path.exists(temp_bin): 
                # Próba nadania uprawnień wykonywania (ważne dla Linux/macOS po rozpakowaniu z OneFile)
                try:
                    os.chmod(temp_bin, 0o755)
                except:
                    pass
                self.ai_tool_path = temp_bin
                return True
                
        return False

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=ME_BLACK)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(50, weight=1) # Spacer na dole

        current_row = 0

        self.lbl_app_title = ctk.CTkLabel(self.sidebar, text="Asystent PIM", font=ctk.CTkFont(size=24, weight="bold"), text_color=ME_YELLOW)
        self.lbl_app_title.grid(row=current_row, column=0, padx=20, pady=(20, 10))
        self.sidebar_widgets['lbl_app_title'] = {'widget': self.lbl_app_title, 'row': current_row}
        current_row += 1
        
        self.lbl_me_expert = ctk.CTkLabel(self.sidebar, text="MEDIA EXPERT", font=ctk.CTkFont(size=12, weight="bold"), text_color="white")
        self.lbl_me_expert.grid(row=current_row, column=0, padx=20, pady=(0, 20))
        self.sidebar_widgets['lbl_me_expert'] = {'widget': self.lbl_me_expert, 'row': current_row}
        current_row += 1

        btn_me = {"width": 200, "height": 40, "corner_radius": 4, "fg_color": ME_YELLOW, "text_color": ME_TEXT_ON_YELLOW, "hover_color": ME_YELLOW_HOVER, "font": ctk.CTkFont(weight="bold")}
        
        # BLOK 1: GŁÓWNE
        self.lbl_b1 = ctk.CTkLabel(self.sidebar, text="GŁÓWNE", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50")
        self.lbl_b1.grid(row=current_row, column=0, sticky="w", padx=20, pady=(5,0))
        self.sidebar_widgets['lbl_b1'] = {'widget': self.lbl_b1, 'row': current_row}
        current_row += 1

        self.btn_add = ctk.CTkButton(self.sidebar, text="DODAJ OBRAZY", command=self.add_images, **btn_me)
        self.btn_add.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_add'] = {'widget': self.btn_add, 'row': current_row}
        current_row += 1
        
        self.btn_clear = ctk.CTkButton(self.sidebar, text="WYCZYŚĆ LISTĘ", command=self.clear_list, fg_color="#444444", text_color="white", hover_color="#666666", width=200, height=35)
        self.btn_clear.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_clear'] = {'widget': self.btn_clear, 'row': current_row}
        current_row += 1
        
        self.btn_remove = ctk.CTkButton(self.sidebar, text="USUŃ ZAZNACZONY", command=self.remove_selected, fg_color="transparent", border_width=1, border_color="gray50", text_color="gray80", width=200)
        self.btn_remove.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_remove'] = {'widget': self.btn_remove, 'row': current_row}
        current_row += 1

        self.frame_order = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_order.grid(row=current_row, column=0, pady=5)
        self.sidebar_widgets['frame_order'] = {'widget': self.frame_order, 'row': current_row}
        self.lbl_order = ctk.CTkLabel(self.frame_order, text="KOLEJNOŚĆ", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray")
        self.lbl_order.pack(side="top")
        self.btn_up = ctk.CTkButton(self.frame_order, text="▲", command=self.move_up, width=95, height=30, fg_color="#444444", hover_color="#666666")
        self.btn_up.pack(side="left", padx=5)
        self.btn_down = ctk.CTkButton(self.frame_order, text="▼", command=self.move_down, width=95, height=30, fg_color="#444444", hover_color="#666666")
        self.btn_down.pack(side="left", padx=5)
        current_row += 1

        # BLOK 2: USTAWIENIA
        self.lbl_b2 = ctk.CTkLabel(self.sidebar, text="USTAWIENIA", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50")
        self.lbl_b2.grid(row=current_row, column=0, sticky="w", padx=20, pady=(15,0))
        self.sidebar_widgets['lbl_b2'] = {'widget': self.lbl_b2, 'row': current_row}
        current_row += 1

        self.frame_quality = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_quality.grid(row=current_row, column=0, pady=5)
        self.sidebar_widgets['frame_quality'] = {'widget': self.frame_quality, 'row': current_row}
        self.lbl_quality = ctk.CTkLabel(self.frame_quality, text="Jakość: 100", text_color="white")
        self.lbl_quality.pack()
        self.slider_quality = ctk.CTkSlider(self.frame_quality, from_=10, to=100, number_of_steps=90, command=self.update_quality_label, width=180, progress_color=ME_YELLOW, button_color="white", button_hover_color=ME_YELLOW)
        self.slider_quality.set(100)
        self.slider_quality.pack()
        current_row += 1

        self.chk_overwrite = ctk.CTkCheckBox(self.sidebar, text="Nadpisz pliki", variable=self.overwrite_var, font=ctk.CTkFont(size=12), text_color="white", fg_color=ME_YELLOW, hover_color=ME_YELLOW_HOVER, checkmark_color="black")
        self.chk_overwrite.grid(row=current_row, column=0, padx=25, pady=5, sticky="w")
        self.sidebar_widgets['chk_overwrite'] = {'widget': self.chk_overwrite, 'row': current_row}
        current_row += 1

        # BLOK 3: KONWERSJA
        self.lbl_b3 = ctk.CTkLabel(self.sidebar, text="KONWERSJA", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50")
        self.lbl_b3.grid(row=current_row, column=0, sticky="w", padx=20, pady=(15,0))
        self.sidebar_widgets['lbl_b3'] = {'widget': self.lbl_b3, 'row': current_row}
        current_row += 1

        self.btn_jpg = ctk.CTkButton(self.sidebar, text="KONWERTUJ DO JPG", command=self.convert_to_jpg, **btn_me)
        self.btn_jpg.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_jpg'] = {'widget': self.btn_jpg, 'row': current_row}
        current_row += 1
        
        self.btn_webp = ctk.CTkButton(self.sidebar, text="KONWERTUJ DO WEBP", command=self.convert_to_webp, **btn_me)
        self.btn_webp.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_webp'] = {'widget': self.btn_webp, 'row': current_row}
        current_row += 1

        # BLOK 4: EDYCJA I SKALOWANIE
        self.lbl_b4 = ctk.CTkLabel(self.sidebar, text="EDYCJA I SKALOWANIE", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50")
        self.lbl_b4.grid(row=current_row, column=0, sticky="w", padx=20, pady=(15,0))
        self.sidebar_widgets['lbl_b4'] = {'widget': self.lbl_b4, 'row': current_row}
        current_row += 1

        self.btn_white_bg = ctk.CTkButton(self.sidebar, text="DODAJ BIAŁE TŁO", command=self.add_white_bg, **btn_me)
        self.btn_white_bg.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_white_bg'] = {'widget': self.btn_white_bg, 'row': current_row}
        current_row += 1

        self.btn_border = ctk.CTkButton(self.sidebar, text="DODAJ RAMKĘ 5px", command=self.add_border_5px, **btn_me)
        self.btn_border.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_border'] = {'widget': self.btn_border, 'row': current_row}
        current_row += 1

        self.btn_crop = ctk.CTkButton(self.sidebar, text="KADRUJ", command=self.auto_crop, **btn_me)
        self.btn_crop.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_crop'] = {'widget': self.btn_crop, 'row': current_row}
        current_row += 1

        self.btn_upscale = ctk.CTkButton(self.sidebar, text="ZWIĘKSZ DO 500px", command=self.upscale_500, **btn_me)
        self.btn_upscale.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_upscale'] = {'widget': self.btn_upscale, 'row': current_row}
        current_row += 1

        self.btn_downscale = ctk.CTkButton(self.sidebar, text="DOPASUJ DO 3000x3600", command=self.downscale_custom, **btn_me)
        self.btn_downscale.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_downscale'] = {'widget': self.btn_downscale, 'row': current_row}
        current_row += 1

        self.btn_compress = ctk.CTkButton(self.sidebar, text="KOMPRESUJ DO 3 MB", command=self.smart_compress_3mb, **btn_me)
        self.btn_compress.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_compress'] = {'widget': self.btn_compress, 'row': current_row}
        current_row += 1

        has_ai = self.check_ai_tools()
        if has_ai:
            self.frame_ai = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            self.frame_ai.grid(row=current_row, column=0, pady=(5,0))
            self.sidebar_widgets['frame_ai_settings'] = {'widget': self.frame_ai, 'row': current_row} 
            ctk.CTkLabel(self.frame_ai, text="Max Px:", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
            self.entry_ai_target = ctk.CTkEntry(self.frame_ai, width=60, height=25, border_color="#6A0DAD", justify="center")
            self.entry_ai_target.insert(0, "3000")
            self.entry_ai_target.pack(side="left", padx=2)
            current_row += 1
            
            btn_ai = btn_me.copy()
            btn_ai.update({"fg_color": "#6A0DAD", "hover_color": "#800080"})
            self.btn_ai = ctk.CTkButton(self.sidebar, text="AI SMART UPSCALE", command=self.ai_upscale_x4, **btn_ai)
            self.btn_ai.grid(row=current_row, column=0, padx=15, pady=5)
            self.sidebar_widgets['btn_ai'] = {'widget': self.btn_ai, 'row': current_row}
            current_row += 1
        else:
            self.lbl_no_ai = ctk.CTkLabel(self.sidebar, text="(Brak pluginu AI)", font=ctk.CTkFont(size=10), text_color="gray")
            self.lbl_no_ai.grid(row=current_row, column=0)
            self.sidebar_widgets['lbl_no_ai'] = {'widget': self.lbl_no_ai, 'row': current_row}
            current_row += 1

        # MAIN AREA
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_area.grid_rowconfigure(2, weight=1)
        self.main_area.grid_columnconfigure(0, weight=2)
        self.main_area.grid_columnconfigure(1, weight=3)

        self.top_frame = ctk.CTkFrame(self.main_area, corner_radius=0, fg_color="#222222")
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        ctk.CTkLabel(self.top_frame, text="Nazwa:", font=ctk.CTkFont(weight="bold"), text_color="white").pack(side="left", padx=(20, 5), pady=15)
        self.entry_name = ctk.CTkEntry(self.top_frame, width=300, placeholder_text="Nazwa produktu...", border_color=ME_YELLOW)
        self.entry_name.pack(side="left", padx=5, pady=15)
        ctk.CTkButton(self.top_frame, text="WKLEJ", command=self.paste_from_clipboard, width=50, fg_color="#444444", hover_color="#666666").pack(side="left", padx=5)
        
        ctk.CTkLabel(self.top_frame, text="Start nr:", font=ctk.CTkFont(weight="bold"), text_color="white").pack(side="left", padx=(15, 5))
        self.entry_start_num = ctk.CTkEntry(self.top_frame, width=50, border_color=ME_YELLOW, justify="center")
        self.entry_start_num.insert(0, "1")
        self.entry_start_num.pack(side="left", padx=5)

        ctk.CTkButton(self.top_frame, text="ZMIEŃ NAZWY (ZAZNACZONE)", command=self.rename_files, fg_color="#2CC937", text_color="black", width=200, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=20, pady=15)

        self.list_frame = ctk.CTkFrame(self.main_area, corner_radius=10, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=15)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(1, weight=1)
        
        self.list_frame.bind("<Double-Button-1>", lambda e: self.add_images())

        ctk.CTkLabel(self.list_frame, text="Lista plików", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=0, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=30, fieldbackground="#2b2b2b", borderwidth=0, font=("Segoe UI", 10))
        style.map('Treeview', background=[('selected', ME_YELLOW)], foreground=[('selected', 'black')])
        style.configure("Treeview.Heading", background="#333333", foreground="white", relief="flat", font=("Segoe UI", 10, "bold"))
        
        self.tree = ttk.Treeview(self.list_frame, columns=("chk", "lp", "nazwa", "rozmiar", "wymiar", "akcja"), show="headings", selectmode="extended")
        self.tree.heading("chk", text="Zmień", anchor="center")
        self.tree.heading("lp", text="Lp.", anchor="center")
        self.tree.heading("nazwa", text="Nazwa pliku", anchor="w")
        self.tree.heading("rozmiar", text="Rozmiar", anchor="center")
        self.tree.heading("wymiar", text="Wymiar", anchor="center")
        self.tree.heading("akcja", text="Folder", anchor="center")
        
        self.tree.column("chk", width=50, anchor="center")
        self.tree.column("lp", width=40, anchor="center")
        self.tree.column("nazwa", width=250)
        self.tree.column("rozmiar", width=80)
        self.tree.column("wymiar", width=100)
        self.tree.column("akcja", width=50, anchor="center")
        
        self.tree.grid(row=1, column=0, sticky="nsew")
        
        scrollbar = ctk.CTkScrollbar(self.list_frame, command=self.tree.yview, fg_color="transparent", button_color="#444444", button_hover_color="#666666")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-Button-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        
        if platform.system() == "Darwin":
            self.tree.bind("<Button-2>", self.show_context_menu)
            self.tree.bind("<Control-Button-1>", self.show_context_menu)

        self.context_menu = Menu(self.main_area, tearoff=0, bg="#2D2D2D", fg="white", activebackground=ME_YELLOW, activeforeground="black")
        self.context_menu.add_command(label="Otwórz plik", command=self.open_file_default)
        self.context_menu.add_command(label="Otwórz folder pliku", command=self.open_folder_context)
        self.context_menu.add_command(label="Edytuj w GIMP", command=self.open_in_gimp)
        self.context_menu.add_command(label="Edytuj obraz (domyślnie)", command=self.edit_default_image) # NOWA OPCJA
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Zapisz zaznaczone do ZIP", command=self.save_to_zip)
        self.context_menu.add_command(label="Zapisz zaznaczone do 7z", command=self.save_to_7z) # NOWA OPCJA
        self.context_menu.add_command(label="Usuń z listy", command=self.remove_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Zakończ", command=self.quit)

        self.preview_frame = ctk.CTkFrame(self.main_area, corner_radius=0, fg_color="#222222")
        self.preview_frame.grid(row=2, column=1, sticky="nsew", padx=15, pady=15)
        self.preview_frame.grid_propagate(False)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=0)
        self.preview_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.preview_frame, text="Podgląd", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, pady=10)
        self.lbl_preview = tk.Label(self.preview_frame, text="Wybierz plik", fg="gray", bg="#222222", font=("Segoe UI", 10))
        self.lbl_preview.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.lbl_preview.bind("<Button-1>", self.open_preview_file)
        
        self.preview_frame.bind("<Configure>", self.resize_preview_event)

        self.status_label = ctk.CTkLabel(self.main_area, text="Gotowy", anchor="w", text_color="gray")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5,10), padx=20)

    def create_main_menu(self):
        menubar = Menu(self)
        self.config(menu=menubar)
        
        # Menu Plik
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Plik", menu=file_menu)
        file_menu.add_command(label="Dodaj obrazy", command=self.add_images)
        file_menu.add_command(label="Dodaj folder", command=self.add_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Zakończ", command=self.quit)

        # Menu Widok
        view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Widok", menu=view_menu)
        
        def add_toggle(label, widget_key, default=True):
            var = tk.BooleanVar(value=default)
            self.view_vars[label] = var
            widget_data = self.sidebar_widgets.get(widget_key)
            if widget_data:
                widget = widget_data['widget']
                # command wywołuje toggle_widget z konkretnymi argumentami
                view_menu.add_checkbutton(label=label, variable=var, 
                                          command=lambda w=widget, v=var, k=widget_key: self.toggle_widget(w, v, k))
                # Initial state based on default value
                if not default:
                    widget.grid_remove()
            else:
                # Obsługa widgetów, które mogą nie istnieć (np. AI)
                view_menu.add_checkbutton(label=label, variable=var, state='disabled',
                                          command=lambda: print(f"Widget {widget_key} not found"))
            return var

        # Nagłówek Aplikacji
        add_toggle("Nagłówek aplikacji", 'lbl_app_title')
        add_toggle("Media Expert Logo", 'lbl_me_expert', default=False)

        # BLOK 1: GŁÓWNE
        view_menu.add_command(label="--- Główne ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b1')
        add_toggle("Dodaj obrazy", 'btn_add')
        add_toggle("Wyczyść listę", 'btn_clear')
        add_toggle("Usuń zaznaczenie", 'btn_remove')
        add_toggle("Kolejność (przyciski)", 'frame_order') 
        
        # BLOK 2: USTAWIENIA
        view_menu.add_separator()
        view_menu.add_command(label="--- Ustawienia ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b2')
        add_toggle("Jakość JPG (slider)", 'frame_quality')
        add_toggle("Nadpisz pliki (checkbox)", 'chk_overwrite')
        
        # BLOK 3: KONWERSJA
        view_menu.add_separator()
        view_menu.add_command(label="--- Konwersja ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b3')
        add_toggle("Konwertuj do JPG", 'btn_jpg')
        add_toggle("Konwertuj do WebP", 'btn_webp', default=False)
        
        # BLOK 4: EDYCJA I SKALOWANIE
        view_menu.add_separator()
        view_menu.add_command(label="--- Edycja i Skalowanie ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b4')
        add_toggle("Dodaj białe tło", 'btn_white_bg')
        add_toggle("Dodaj ramkę", 'btn_border')
        add_toggle("Kadruj", 'btn_crop')
        add_toggle("Zwiększ do 500px", 'btn_upscale')
        add_toggle("Dopasuj 3000x3600", 'btn_downscale')
        add_toggle("Kompresuj do 3 MB", 'btn_compress')
        
        if hasattr(self, 'btn_ai'): # Sprawdź czy AI jest dostępne, zanim dodasz do menu
            view_menu.add_separator()
            add_toggle("AI Smart Upscale", 'btn_ai')
            add_toggle("AI Settings", 'frame_ai_settings') # Ukrywa label i entry AI

        # Menu About
        about_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="About", menu=about_menu)
        about_menu.add_command(label="Asystent PIM", state='disabled')
        about_menu.add_command(label="Media Expert", command=self.open_me_website)

    def toggle_widget(self, widget, var, widget_key):
        if var.get():
            widget.grid() # grid() przywraca widget z zapamiętanymi opcjami
        else:
            widget.grid_remove() # grid_remove() ukrywa, ale pamięta opcje

    def open_me_website(self):
        webbrowser.open_new("https://www.mediaexpert.pl")

    def open_preview_file(self, event):
        if self.current_preview_path and os.path.exists(self.current_preview_path):
            self.open_path(self.current_preview_path)

    def on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            self.add_images()

    def update_quality_label(self, value):
        self.lbl_quality.configure(text=f"Jakość: {int(value)}")

    def hide_context_menu(self, event):
        try: self.context_menu.unpost()
        except: pass

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
        
        try:
            start_num = int(self.entry_start_num.get())
        except ValueError:
            start_num = 1
            self.entry_start_num.delete(0, tk.END)
            self.entry_start_num.insert(0, "1")

        items = self.tree.get_children()
        if not items: return
        
        current_num = start_num
        renamed_count = 0
        
        for item in items:
            vals = self.tree.item(item)['values']
            should_rename = (vals[0] == "☑") # Sprawdź status checkboxa
            
            if not should_rename:
                # Jeśli odznaczony, tylko zaktualizuj Lp. (opcjonalnie) lub pomiń
                continue

            old_path = self.tree.item(item)['tags'][0]
            if not os.path.exists(old_path): continue
            
            folder = os.path.dirname(old_path)
            ext = os.path.splitext(old_path)[1]
            new_filename = f"{clean_base}-{current_num}{ext}"
            new_path = os.path.join(folder, new_filename)
            
            if old_path != new_path:
                try:
                    os.rename(old_path, new_path)
                    size = os.path.getsize(new_path)
                    name = os.path.basename(new_path)
                    dim = vals[4]
                    # Zachowaj checkbox zaznaczony
                    self.tree.item(item, values=("☑", vals[1], name, self.format_bytes(size), dim, "📂"), tags=[new_path])
                    renamed_count += 1
                except Exception as e: print(f"Rename err: {e}")
            
            current_num += 1

        self.update_indexes()
        self.status_label.configure(text=f"Zmieniono nazwy dla {renamed_count} plików.")

    def on_tree_click(self, event):
        self.hide_context_menu(event)
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            row_id = self.tree.identify_row(event.y)
            if not row_id: return
            
            # Obsługa kliknięcia w checkbox (kolumna #1 to 'chk')
            if column == "#1":
                self.toggle_check(row_id)
            elif column == "#6": # Teraz folder to kolumna 6
                file_path = self.tree.item(row_id)['tags'][0]
                self.open_file_location(file_path)
            else:
                file_path = self.tree.item(row_id)['tags'][0]
                self.show_preview(file_path)

    def toggle_check(self, item_id):
        current = self.tree.item(item_id)['values'][0]
        new_val = "☐" if current == "☑" else "☑"
        vals = list(self.tree.item(item_id)['values'])
        vals[0] = new_val
        self.tree.item(item_id, values=tuple(vals))

    def resize_preview_event(self, event):
        # Wywoływane gdy ramka podglądu zmienia rozmiar
        if self.current_preview_path:
            self.show_preview(self.current_preview_path)

    def show_context_menu(self, event):
        try:
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
                self.context_menu.tk_popup(event.x_root, event.y_root)
        except: pass

    def open_file_default(self):
        sel = self.tree.selection()
        if sel: self.open_path(self.tree.item(sel[0])['tags'][0])

    def open_folder_context(self):
        sel = self.tree.selection()
        if sel: self.open_file_location(self.tree.item(sel[0])['tags'][0])

    def open_in_gimp(self):
        sel = self.tree.selection()
        if sel:
            path = self.tree.item(sel[0])['tags'][0]
            if not os.path.exists(path): return
            
            if platform.system() == "Darwin":
                try:
                    subprocess.Popen(['open', '-a', 'GIMP', path])
                except Exception as e:
                    messagebox.showerror("Błąd", f"Nie udało się uruchomić GIMP na macOS: {e}\nSprawdź, czy GIMP jest zainstalowany i dostępny w folderze /Applications.")
            else:
                try:
                    subprocess.Popen(['gimp', path])
                except FileNotFoundError:
                    try: subprocess.Popen(['flatpak', 'run', 'org.gimp.GIMP', path])
                    except: messagebox.showerror("Błąd", "Nie znaleziono programu GIMP (Linux/Windows).")

    def edit_default_image(self): # NOWA METODA
        sel = self.tree.selection()
        if sel:
            path = self.tree.item(sel[0])['tags'][0]
            if not os.path.exists(path): return
            self.open_path(path) # Używa istniejącej metody do otwierania domyślnego

    def save_to_zip(self):
        selected = self.tree.selection()
        if not selected: return messagebox.showwarning("Info", "Wybierz pliki do spakowania.")
        
        target_zip = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Plik ZIP", "*.zip")], title="Zapisz jako ZIP")
        if not target_zip: return

        count = 0
        try:
            with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for item in selected:
                    path = self.tree.item(item)['tags'][0]
                    if os.path.exists(path):
                        zf.write(path, os.path.basename(path))
                        count += 1
            self.status_label.configure(text=f"Zapisano {count} plików do {os.path.basename(target_zip)}")
            messagebox.showinfo("Sukces", f"Utworzono archiwum ZIP:\n{target_zip}")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się utworzyć ZIP: {e}")

    def save_to_7z(self): # NOWA METODA
        selected = self.tree.selection()
        if not selected: return messagebox.showwarning("Info", "Wybierz pliki do spakowania.")
        
        # Sprawdź dostępność 7z w systemie
        sevenz_path = shutil.which('7z')
        if not sevenz_path:
            messagebox.showerror("Błąd", "Nie znaleziono programu '7z' w systemie.\nUpewnij się, że '7z' (p7zip) jest zainstalowany i dostępny w PATH.")
            return

        target_7z = filedialog.asksaveasfilename(defaultextension=".7z", filetypes=[("Archiwum 7z", "*.7z")], title="Zapisz jako 7z")
        if not target_7z: return

        files_to_compress = [self.tree.item(item)['tags'][0] for item in selected if os.path.exists(self.tree.item(item)['tags'][0])]
        
        try:
            # Komenda: 7z a -t7z archiwum.7z plik1 plik2 ...
            cmd = [sevenz_path, 'a', '-t7z', target_7z] + files_to_compress
            
            # Uruchomienie procesu z ukrytą konsolą na Windows
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(cmd, check=True, startupinfo=startupinfo)
            self.status_label.configure(text=f"Zapisano {len(files_to_compress)} plików do {os.path.basename(target_7z)}")
            messagebox.showinfo("Sukces", f"Utworzono archiwum 7z:\n{target_7z}")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Błąd 7z", f"Błąd podczas tworzenia archiwum 7z: {e}\n{e.stderr.decode()}")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się utworzyć 7z: {e}")

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
            
            # Pobierz aktualne wymiary ramki podglądu
            frame_w = self.preview_frame.winfo_width()
            frame_h = self.preview_frame.winfo_height()
            
            # Jeśli ramka jest zbyt mała (np. przy starcie), ustaw domyślne minimum
            if frame_w < 50: frame_w = 400
            if frame_h < 50: frame_h = 400

            # Odejmij marginesy
            max_w = frame_w - 20
            max_h = frame_h - 40 # trochę więcej na etykietę "Podgląd"

            self.lbl_preview.configure(image="", text="Ładowanie...")
            # self.update_idletasks() # Może powodować migotanie przy resize, opcjonalne

            pil_image = Image.open(file_path)
            w, h = pil_image.size
            
            # Skalowanie z zachowaniem proporcji
            r = min(max_w/w, max_h/h)
            new_w = int(w * r)
            new_h = int(h * r)
            
            # Zapobiegaj skalowaniu w górę jeśli obraz jest mniejszy niż ramka (opcjonalne, tutaj skalujemy w dół)
            # if r > 1: r = 1 ...
            
            resized = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            tk_image = ImageTk.PhotoImage(resized)
            self.preview_image_ref = tk_image
            self.lbl_preview.configure(image=tk_image, text="")
            self.current_preview_path = file_path
        except Exception as e:
            # print(f"Preview err: {e}")
            self.lbl_preview.configure(image="", text="Błąd wyświetlania")

    def add_images(self):
        types = [("Obrazy", "*.jpg *.jpeg *.png *.bmp *.webp *.heic *.avif *.tif *.tiff *.JPG *.JPEG *.PNG *.BMP *.WEBP *.HEIC *.AVIF *.TIF *.TIFF")]
        files = filedialog.askopenfilenames(filetypes=types)
        if files: self.process_added_files(files)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        
        # Rozszerzenia obsługiwane (małymi literami)
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.heic', '.avif', '.tif', '.tiff')
        
        files = []
        try:
            for f in os.listdir(folder):
                if f.lower().endswith(exts):
                    full_path = os.path.join(folder, f)
                    if os.path.isfile(full_path):
                        files.append(full_path)
        except Exception as e:
            print(f"Error reading folder: {e}")
            
        if files:
            self.process_added_files(files)

    def process_added_files(self, files):
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
            # Dodano "☑" jako wartość dla kolumny "chk"
            self.tree.insert("", "end", values=("☑", "", name, self.format_bytes(size), res, "📂"), tags=[path])
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
        quality_val = int(self.slider_quality.get())

        for item in selected:
            path = self.tree.item(item)['tags'][0]
            if not os.path.exists(path): continue

            try:
                with Image.open(path) as img:
                    img.load()
                    res = func(img)
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
                                if name == "JPG" or name == "Kompresja3MB" or name == "WEBP":
                                    # Dla formatów zmieniających rozszerzenie
                                    pass 
                                else:
                                    save_path = f"{n}_{suffix}{e}"
                            except Exception as e:
                                continue
                        
                        # Obsługa formatów i zapisu
                        if name == "JPG":
                            if res.mode != 'RGB': res = res.convert('RGB')
                            root, _ = os.path.splitext(save_path)
                            save_path = root + ".jpg"
                            res.save(save_path, quality=quality_val, optimize=True, progressive=True)
                        
                        elif name == "WEBP":
                            root, _ = os.path.splitext(save_path)
                            save_path = root + ".webp"
                            # WebP wspiera przezroczystość, nie konwertujemy do RGB
                            res.save(save_path, quality=quality_val, optimize=True)

                        elif name == "Kompresja3MB":
                            if res.mode != 'RGB': res = res.convert('RGB')
                            root, _ = os.path.splitext(save_path)
                            save_path = root + ".jpg"
                            self.save_compressed_limit(res, save_path, 3 * 1024 * 1024)
                        
                        else:
                            # Inne operacje (zachowaj format lub jpg jeśli wymuszone)
                            if save_path.lower().endswith(('.jpg', '.jpeg')):
                                if res.mode != 'RGB': res = res.convert('RGB')
                                res.save(save_path, quality=quality_val, optimize=True, progressive=True)
                            else:
                                res.save(save_path)

                        if os.path.exists(save_path):
                            if not overwrite:
                                self.file_list.remove(path)
                                self.file_list.append(save_path)
                            
                            size = os.path.getsize(save_path)
                            dim = f"{res.width}x{res.height} px"
                            vals = self.tree.item(item)['values']
                            # Zachowaj stan checkboxa (vals[0])
                            self.tree.item(item, values=(vals[0], vals[1], os.path.basename(save_path), self.format_bytes(size), dim, "📂"), tags=[save_path])
                            if self.current_preview_path == path: self.show_preview(save_path)

            except Exception as e:
                self.status_label.configure(text=f"Błąd: {os.path.basename(path)}")

        self.update_indexes()
        self.status_label.configure(text=f"Zakończono: {name}")

    def save_compressed_limit(self, img, path, limit_bytes):
        quality = 95
        min_quality = 65
        while quality >= min_quality:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            if buffer.getbuffer().nbytes <= limit_bytes:
                with open(path, "wb") as f: f.write(buffer.getbuffer())
                return
            quality -= 5
        scale = 0.9
        while True:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            if new_w < 100 or new_h < 100: break
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=min_quality, optimize=True, progressive=True)
            if buffer.getbuffer().nbytes <= limit_bytes:
                with open(path, "wb") as f: f.write(buffer.getbuffer())
                return
            scale *= 0.9

    def ai_upscale_x4(self):
        selected = self.tree.selection()
        if not selected: return messagebox.showwarning("Info", "Wybierz pliki.")
        if not hasattr(self, 'ai_tool_path') or not self.ai_tool_path:
             return messagebox.showerror("Błąd", "Nie znaleziono narzędzia AI (realesrgan-ncnn-vulkan).")

        # Pobierz cel w pikselach
        try:
            target_px = int(self.entry_ai_target.get())
        except ValueError:
            target_px = 3000 # Fallback

        overwrite = self.overwrite_var.get()
        self.status_label.configure(text=f"Przetwarzanie AI Smart x2 (Max {target_px}px)...")
        self.update_idletasks()

        processed_count = 0
        
        for item in selected:
            path = self.tree.item(item)['tags'][0]
            if not os.path.exists(path): continue
            
            try:
                original_dir = os.path.dirname(path)
                filename = os.path.basename(path)
                name_root, ext = os.path.splitext(filename)
                
                # Zawsze tworzymy plik tymczasowy po AI
                temp_ai_out = os.path.join(original_dir, f"{name_root}_ai_raw{ext}")

                cmd = [
                    self.ai_tool_path,
                    "-i", path,
                    "-o", temp_ai_out,
                    "-s", "2", # Zmiana na x2
                    "-n", "realesr-animevideov3-x2" # Jawny model x2
                ]
                
                # Jeśli uruchamiamy z OneFile, modele są w katalogu tymczasowym.
                # Realesrgan szuka modeli w folderze 'models' obok siebie lub wskazanym przez -m
                if hasattr(sys, '_MEIPASS'):
                    # Wskazujemy folder models wewnątrz temp
                    models_path = os.path.join(sys._MEIPASS, "models")
                    cmd.extend(["-m", models_path])

                startupinfo = None
                if platform.system() == "Windows":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                my_env = os.environ.copy()
                if 'LD_LIBRARY_PATH' in my_env: del my_env['LD_LIBRARY_PATH']

                subprocess.run(cmd, check=True, startupinfo=startupinfo, env=my_env)
                
                if not os.path.exists(temp_ai_out):
                    raise Exception("AI failed output")

                # Krok 2: Smart Downscale (jeśli potrzebny)
                final_image_path = temp_ai_out # Domyślnie bierzemy surowy wynik AI
                
                try:
                    with Image.open(temp_ai_out) as img:
                        w, h = img.size
                        # Sprawdź czy trzeba zmniejszyć
                        if max(w, h) > target_px:
                            scale = target_px / max(w, h)
                            new_w = int(w * scale)
                            new_h = int(h * scale)
                            # Wysokiej jakości downscale
                            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            # Nadpisz tymczasowy
                            resized.save(temp_ai_out)
                except Exception as e:
                    print(f"Smart Resize Err: {e}")

                # Krok 3: Finalizacja (Nadpisz lub Nowy Plik)
                if overwrite:
                    orig_archive_dir = os.path.join(original_dir, "_orig")
                    os.makedirs(orig_archive_dir, exist_ok=True)
                    archived_path = os.path.join(original_dir, filename)
                    
                    if not os.path.exists(archived_path):
                        os.rename(path, archived_path)
                    else:
                        os.remove(path)
                    
                    os.rename(temp_ai_out, path)
                    final_result_path = path
                else:
                    new_filename = f"{name_root}_SmartAI{ext}"
                    save_path = os.path.join(original_dir, new_filename)
                    if os.path.exists(save_path): os.remove(save_path)
                    os.rename(temp_ai_out, save_path)
                    final_result_path = save_path

                # GUI Update
                if os.path.exists(final_result_path):
                    size = os.path.getsize(final_result_path)
                    with Image.open(final_result_path) as img:
                        dim = f"{img.width}x{img.height} px"
                    
                    vals = self.tree.item(item)['values']
                    if overwrite:
                         self.tree.item(item, values=(vals[0], vals[1], os.path.basename(final_result_path), self.format_bytes(size), dim, "📂"), tags=[final_result_path])
                         if self.current_preview_path == path: self.show_preview(final_result_path)
                    else:
                        self.file_list.remove(path)
                        self.file_list.append(final_result_path)
                        self.tree.item(item, values=(vals[0], vals[1], os.path.basename(final_result_path), self.format_bytes(size), dim, "📂"), tags=[final_result_path])

                    processed_count += 1

            except Exception as e:
                print(f"AI Error: {e}")
                self.status_label.configure(text=f"Błąd AI: {os.path.basename(path)}")
                # Sprzątaj temp
                try: 
                    if 'temp_ai_out' in locals() and os.path.exists(temp_ai_out): os.remove(temp_ai_out)
                except: pass
        
        self.update_indexes()
        self.status_label.configure(text=f"Zakończono Smart AI: {processed_count} plików.")

    def convert_to_jpg(self): self.process_images("JPG", lambda i: i.convert("RGB"))
    def convert_to_webp(self): self.process_images("WEBP", lambda i: i)
    def smart_compress_3mb(self): self.process_images("Kompresja3MB", lambda i: i)
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
                new_w = max(w, 500)
                new_h = max(h, 500)
                if i.mode == 'RGBA':
                    bg = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
                    x = (new_w - w) // 2
                    y = (new_h - h) // 2
                    bg.paste(i, (x, y), i)
                    return bg
                else:
                    bg = Image.new("RGB", (new_w, new_h), "white")
                    x = (new_w - w) // 2
                    y = (new_h - h) // 2
                    bg.paste(i, (x, y))
                    return bg
            return i
        self.process_images("Upscale(Tło)", f)
    def downscale_custom(self):
        def f(i):
            w, h = i.size
            if w > 3000 or h > 3600:
                i.thumbnail((3000, 3600), Image.Resampling.LANCZOS)
                return i
            return i
        self.process_images("Downscale", f)

if __name__ == "__main__":
    app = AsystentApp()
    app.mainloop()