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
import cv2
import numpy as np
from gradio_client import Client 
import urllib.parse
import requests
import base64
import configparser
import webbrowser

# Wyłącz limit pikseli dla dużych obrazów z AI
Image.MAX_IMAGE_PIXELS = None

pillow_heif.register_heif_opener()

ctk.set_appearance_mode("Dark")
ME_YELLOW = "#FFCC00"
ME_YELLOW_HOVER = "#E6B800"
ME_BLACK = "#2D2D2D"
ME_TEXT_ON_YELLOW = "black"

class ErrorDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x400")
        self.message = message
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.textbox.insert("0.0", message)
        self.textbox.configure(state="disabled")

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.btn_copy = ctk.CTkButton(self.btn_frame, text="Kopiuj do schowka", command=self.copy_to_clipboard, fg_color="#444444", hover_color="#666666")
        self.btn_copy.pack(side="left", padx=5)

        self.btn_send = ctk.CTkButton(self.btn_frame, text="Wyślij zgłoszenie", command=self.send_report, fg_color=ME_YELLOW, text_color="black", hover_color=ME_YELLOW_HOVER)
        self.btn_send.pack(side="right", padx=5)

        self.btn_close = ctk.CTkButton(self.btn_frame, text="Zamknij", command=self.destroy, fg_color="#444444", hover_color="#666666")
        self.btn_close.pack(side="right", padx=5)

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.message)
        self.update()

    def send_report(self):
        recipient = "dev@lmk.one"
        subject = "Zgłoszenie błędu Asystent PIM"
        body = f"Wystąpił błąd w aplikacji:\n\n{self.message}"
        subject_encoded = urllib.parse.quote(subject)
        body_encoded = urllib.parse.quote(body)
        mailto_link = f"mailto:{recipient}?subject={subject_encoded}&body={body_encoded}"
        webbrowser.open(mailto_link)

    def auto_crop(self):
        def f(i):
            if i.mode != 'RGB': i = i.convert('RGB')
            bw = i.convert("L").point(lambda x: 0 if x >= 240 else 255, '1')
            bbox = bw.getbbox()
            return i.crop(bbox) if bbox else i
        self.process_images("Kadrowanie", f)

class CheckImageDialog(ctk.CTkToplevel):
    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.title("Sprawdź obraz (Inspekcja)")
        self.geometry("1000x800")
        
        # Ładowanie i przetwarzanie
        try:
            img = Image.open(image_path).convert("RGB")
            
            # Ekstremalny kontrast i niska jasność
            from PIL import ImageEnhance
            
            # Kontrast MAX
            enhancer_contrast = ImageEnhance.Contrast(img)
            img = enhancer_contrast.enhance(20.0) 
            
            # Jasność MIN (ale nie czarno)
            enhancer_brightness = ImageEnhance.Brightness(img)
            img = enhancer_brightness.enhance(0.2) 
            
            self.image = img
            
            # Canvas
            self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            
            self.bind("<Configure>", self.resize_event)
            self.bind("<Escape>", lambda e: self.destroy())
            
        except Exception as e:
            messagebox.showerror("Błąd", str(e))
            self.destroy()

    def resize_event(self, event):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10: return
        
        img_w, img_h = self.image.size
        ratio = min(w/img_w, h/img_h)
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        
        self.tk_img = ImageTk.PhotoImage(self.image.resize((new_w, new_h), Image.NEAREST))
        self.canvas.delete("all")
        self.canvas.create_image(w//2, h//2, image=self.tk_img, anchor="center")

class CropEditor(ctk.CTkToplevel):
    def __init__(self, parent, image_path, callback):
        super().__init__(parent)
        self.title("Kadrowanie (Zaznaczenie)")
        self.geometry("1000x800")
        self.image_path = image_path
        self.callback = callback
        
        self.original_image = Image.open(image_path).convert("RGB")
        
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        # UI
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(self.toolbar, text="ZATWIERDŹ", command=self.confirm_crop, fg_color="green", hover_color="darkgreen").pack(side="right", padx=10)
        ctk.CTkButton(self.toolbar, text="Anuluj", command=self.destroy, fg_color="gray").pack(side="right", padx=10)
        ctk.CTkLabel(self.toolbar, text="Zaznacz obszar myszką").pack(side="left", padx=10)

        self.canvas = tk.Canvas(self, bg="#2b2b2b", cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Użyjemy after, aby narysować obraz po otwarciu okna
        self.after(100, self.show_image)
        self.bind("<Configure>", self.resize_event)

    def resize_event(self, event):
        self.show_image()

    def show_image(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10: return
        
        img_w, img_h = self.original_image.size
        
        # Oblicz skalę, aby obraz się zmieścił
        scale_w = w / img_w
        scale_h = h / img_h
        self.scale_factor = min(scale_w, scale_h)
        
        new_w = int(img_w * self.scale_factor)
        new_h = int(img_h * self.scale_factor)
        
        self.tk_img = ImageTk.PhotoImage(self.original_image.resize((new_w, new_h), Image.LANCZOS))
        self.canvas.delete("all")
        
        # Wyśrodkuj
        self.offset_x = (w - new_w) // 2
        self.offset_y = (h - new_h) // 2
        
        self.canvas.create_image(self.offset_x, self.offset_y, image=self.tk_img, anchor="nw")
        
        # Narysuj prostokąt jeśli już istnieje (przy zmianie rozmiaru)
        if self.start_x and self.rect_id:
             # Tutaj trzebaby przeliczyć współrzędne, ale dla uproszczenia zresetujmy
             self.canvas.delete(self.rect_id)
             self.start_x = None

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id: self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_drag(self, event):
        if not self.start_x: return
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        self.end_x = event.x
        self.end_y = event.y

    def confirm_crop(self):
        if not self.start_x or not self.end_x: 
            messagebox.showinfo("Info", "Najpierw zaznacz obszar.")
            return
        
        # Konwersja współrzędnych canvas -> obraz
        x1_c = min(self.start_x, self.end_x)
        y1_c = min(self.start_y, self.end_y)
        x2_c = max(self.start_x, self.end_x)
        y2_c = max(self.start_y, self.end_y)
        
        x1 = (x1_c - self.offset_x) / self.scale_factor
        y1 = (y1_c - self.offset_y) / self.scale_factor
        x2 = (x2_c - self.offset_x) / self.scale_factor
        y2 = (y2_c - self.offset_y) / self.scale_factor
        
        # Clamp
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(self.original_image.width, x2)
        y2 = min(self.original_image.height, y2)
        
        if x2 - x1 < 1 or y2 - y1 < 1: return
        
        cropped = self.original_image.crop((int(x1), int(y1), int(x2), int(y2)))
        self.callback(cropped, self.image_path)
        self.destroy()

class InpaintingEditor(ctk.CTkToplevel):
    def __init__(self, parent, image_path, callback):
        super().__init__(parent)
        self.title("Edytor Inpainting - Zamaluj obiekt")
        self.geometry("1200x850")
        self.image_path = image_path
        self.callback = callback
        
        try:
            self.original_image = Image.open(image_path)
            self.original_image = self.original_image.convert("RGB")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można otworzyć obrazu: {e}")
            self.destroy()
            return

        self.mask_image = Image.new("L", self.original_image.size, 0)
        self.mask_draw = ImageDraw.Draw(self.mask_image)

        self.brush_size = 20
        self.last_x, self.last_y = None, None

        self.setup_ui()
        self.update_canvas()

    def setup_ui(self):
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.pack(side="top", fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.toolbar, text="Pędzel:").pack(side="left", padx=5)
        self.slider_brush = ctk.CTkSlider(self.toolbar, from_=5, to=100, command=self.update_brush_size, width=100)
        self.slider_brush.set(20)
        self.slider_brush.pack(side="left", padx=5)

        # Konfiguracja API
        self.frame_api = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.frame_api.pack(side="left", padx=20)
        
        ctk.CTkLabel(self.frame_api, text="API URL:").pack(side="left", padx=5)
        self.entry_api_url = ctk.CTkEntry(self.frame_api, width=180)
        self.entry_api_url.insert(0, "http://127.0.0.1:7860")
        self.entry_api_url.pack(side="left", padx=5)

        self.btn_process = ctk.CTkButton(self.toolbar, text="WYKONAJ (Lokalne AI)", command=self.process, fg_color=ME_YELLOW, text_color="black", hover_color=ME_YELLOW_HOVER)
        self.btn_process.pack(side="right", padx=10)
        
        self.lbl_status = ctk.CTkLabel(self.toolbar, text="", text_color="gray")
        self.lbl_status.pack(side="right", padx=10)

        self.frame_canvas = ctk.CTkFrame(self)
        self.frame_canvas.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(self.frame_canvas, bg="#333333", highlightthickness=0)
        
        self.scroll_x = ctk.CTkScrollbar(self.frame_canvas, orientation="horizontal", command=self.canvas.xview)
        self.scroll_y = ctk.CTkScrollbar(self.frame_canvas, orientation="vertical", command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=self.scroll_x.set, yscrollcommand=self.scroll_y.set)

        self.scroll_x.pack(side="bottom", fill="x")
        self.scroll_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<ButtonRelease-1>", self.reset_last_point)

    def update_brush_size(self, val):
        self.brush_size = int(val)

    def update_canvas(self):
        self.tk_img = ImageTk.PhotoImage(self.original_image)
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def paint(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        if self.last_x and self.last_y:
            self.canvas.create_line(self.last_x, self.last_y, x, y, width=self.brush_size, fill="red", capstyle=tk.ROUND, smooth=True)
            self.mask_draw.line([self.last_x, self.last_y, x, y], fill=255, width=self.brush_size)
        
        self.last_x = x
        self.last_y = y

    def reset_last_point(self, event):
        self.last_x, self.last_y = None, None

    def image_to_base64(self, img):
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def process(self):
        self.btn_process.configure(state="disabled", text="Przetwarzanie...")
        self.lbl_status.configure(text="Łączenie z lokalnym SD...")
        self.update_idletasks()
        
        api_url = self.entry_api_url.get().strip()
        
        # 1. Próba: Lokalne API Stable Diffusion
        try:
            # Przygotuj payload
            b64_image = self.image_to_base64(self.original_image)
            b64_mask = self.image_to_base64(self.mask_image)
            
            payload = {
                "init_images": [b64_image],
                "mask": b64_mask,
                "prompt": "background, clean, empty, scenery, high quality, realistic",
                "negative_prompt": "low quality, artifacts, watermark, text, object, bad anatomy, person, man, woman",
                "steps": 30,
                "cfg_scale": 7,
                "width": self.original_image.width,
                "height": self.original_image.height,
                "sampler_name": "Euler a",
                "inpainting_fill": 0, # 0=Fill (lepsze do usuwania - zamazuje obiekt kolorami otoczenia)
                "denoising_strength": 0.9,
                "resize_mode": 0
            }

            # Zwiększony timeout dla CPU (3600s = 60 minut)
            response = requests.post(f"{api_url}/sdapi/v1/img2img", json=payload, timeout=3600)
            
            if response.status_code == 200:
                r = response.json()
                result_b64 = r['images'][0]
                result_data = base64.b64decode(result_b64)
                result_pil = Image.open(io.BytesIO(result_data))
                
                self.callback(result_pil, self.image_path)
                self.destroy()
                return
            else:
                raise Exception(f"API Error {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"Local API failed: {e}")
            self.lbl_status.configure(text="Błąd lokalnego API. Przełączanie na tryb offline (OpenCV)...")
            self.update_idletasks()

        # 2. Fallback: OpenCV (Offline)
        try:
            open_cv_image = np.array(self.original_image) 
            open_cv_image = open_cv_image[:, :, ::-1].copy()
            mask = np.array(self.mask_image)

            inpainted = cv2.inpaint(open_cv_image, mask, 3, cv2.INPAINT_TELEA)

            inpainted_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
            result_pil = Image.fromarray(inpainted_rgb)

            self.callback(result_pil, self.image_path)
            
            messagebox.showinfo("Inpainting (Offline)", "Inpainting wykonany przez OpenCV (tryb awaryjny).\nNie udało się połączyć z lokalnym Stable Diffusion.\n\nUpewnij się, że uruchomiłeś A1111 z flagą --api.")
            self.destroy()

        except Exception as e:
            self.lbl_status.configure(text="Błąd krytyczny!")
            self.btn_process.configure(state="normal", text="WYKONAJ (Lokalne AI)")
            error_msg = f"Nie udało się przetworzyć obrazu.\n\nSzczegóły:\n{str(e)}"
            ErrorDialog(self, "Błąd Inpaintingu", error_msg)


class RmbgEditor(ctk.CTkToplevel):
    def __init__(self, parent, image_path, callback, config_manager):
        super().__init__(parent)
        self.title("Usuwanie Tła (RMBG-2.0 Lokalnie)")
        self.geometry("1000x650")
        self.image_path = image_path
        self.callback = callback
        self.config_manager = config_manager
        
        # Load Image
        self.original_image = Image.open(image_path).convert("RGB")
        
        # UI Setup
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.lbl_status = ctk.CTkLabel(self.toolbar, text="Model: briaai/RMBG-2.0 (Non-Commercial)", text_color="gray")
        self.lbl_status.pack(side="left", padx=10)

        # License Info Button / Link
        self.btn_license = ctk.CTkButton(self.toolbar, text="Info o licencji", command=self.show_license_info, width=100, fg_color="transparent", border_width=1, text_color="gray")
        self.btn_license.pack(side="left", padx=5)

        self.btn_process = ctk.CTkButton(self.toolbar, text="USUŃ TŁO", command=self.process, fg_color=ME_YELLOW, text_color="black", hover_color=ME_YELLOW_HOVER)
        self.btn_process.pack(side="right", padx=10)

        # Preview Area
        self.frame_preview = ctk.CTkFrame(self)
        self.frame_preview.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
        
        # Image Display (Before/After)
        self.canvas = tk.Canvas(self.frame_preview, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.after(100, lambda: self.display_image(self.original_image))

    def show_license_info(self):
        webbrowser.open("https://huggingface.co/briaai/RMBG-2.0")

    def display_image(self, img, comparison_img=None):
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 100: w = 800
        if h < 100: h = 500
        
        # Resize logic
        img_ratio = img.width / img.height
        canvas_ratio = w / h
        
        if not comparison_img:
            # Single image centered
            target_w, target_h = w, h
            if img_ratio > canvas_ratio:
                target_w = w
                target_h = int(w / img_ratio)
            else:
                target_h = h
                target_w = int(h * img_ratio)
            
            resized = img.resize((target_w, target_h), Image.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(resized)
            self.canvas.create_image(w//2, h//2, image=self.tk_img, anchor="center")
        else:
            # Side by side
            half_w = w // 2
            
            # Left (Original)
            scale_factor = min(half_w / img.width, h / img.height)
            tw1 = int(img.width * scale_factor)
            th1 = int(img.height * scale_factor)
            res1 = img.resize((tw1, th1), Image.LANCZOS)
            self.tk_img1 = ImageTk.PhotoImage(res1)
            self.canvas.create_image(half_w//2, h//2, image=self.tk_img1, anchor="center")
            self.canvas.create_text(half_w//2, h//2 + th1//2 + 15, text="Oryginał", fill="white")
            
            # Right (Result)
            scale_factor2 = min(half_w / comparison_img.width, h / comparison_img.height)
            tw2 = int(comparison_img.width * scale_factor2)
            th2 = int(comparison_img.height * scale_factor2)
            res2 = comparison_img.resize((tw2, th2), Image.LANCZOS)
            self.tk_img2 = ImageTk.PhotoImage(res2)
            
            # Draw checkerboard pattern for transparency
            self.canvas.create_rectangle(half_w, 0, w, h, fill="#333333", outline="")
            
            self.canvas.create_image(half_w + half_w//2, h//2, image=self.tk_img2, anchor="center")
            self.canvas.create_text(half_w + half_w//2, h//2 + th2//2 + 15, text="RMBG-2.0", fill="white")

    def process(self):
        self.btn_process.configure(state="disabled", text="Przetwarzanie (Lokalnie)...")
        self.lbl_status.configure(text="Uruchamianie lokalnego RMBG-2.0...")
        self.update_idletasks()
        
        import threading
        threading.Thread(target=self._run_local_rmbg).start()

    def _run_local_rmbg(self):
        try:
            print("Uruchamianie RMBG-2.0...")
            import sys
            import subprocess

            temp_output = os.path.join(os.path.dirname(self.image_path), "temp_rmbg_result.png")
            
            # Logika wykrywania środowiska
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
                if platform.system() == "Windows":
                    rmbg_exe = os.path.join(base_path, "rmbg_tool", "rmbg_tool.exe")
                else:
                    rmbg_exe = os.path.join(base_path, "rmbg_tool", "rmbg_tool")
                
                if os.path.exists(rmbg_exe) and platform.system() != "Windows":
                    try: os.chmod(rmbg_exe, 0o755)
                    except: pass

                if not os.path.exists(rmbg_exe):
                     raise Exception(f"Nie znaleziono pliku rmbg_tool w: {base_path}")

                cmd = [rmbg_exe, self.image_path, temp_output]
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                venv_python = os.path.join(script_dir, ".venv_rmbg", "bin", "python")
                script_path = os.path.join(script_dir, "local_rmbg.py")
                
                if not os.path.exists(venv_python): venv_python = sys.executable
                cmd = [venv_python, script_path, self.image_path, temp_output]
            
            # Uruchomienie procesu
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if os.path.exists(temp_output):
                result_pil = Image.open(temp_output)
                self.after(0, lambda: self.finish_success(result_pil))
            elif process.returncode == 0:
                 raise Exception("Skrypt zakończył się sukcesem, ale nie utworzył pliku.")
            else:
                error_log = process.stderr if process.stderr else process.stdout
                raise Exception(f"Błąd skryptu: {error_log}")

        except Exception as e:
            print(f"RMBG Local Error: {e}")
            error_msg = str(e)
            self.after(0, lambda: self.finish_error(error_msg))

    def finish_success(self, result_pil):
        self.lbl_status.configure(text="Sukces!")
        self.display_image(self.original_image, result_pil)
        self.btn_process.configure(text="ZATWIERDŹ I ZAPISZ", command=lambda: self.save_and_close(result_pil), state="normal", fg_color="green", hover_color="darkgreen")

    def finish_error(self, error_msg):
        self.lbl_status.configure(text="Wystąpił błąd.")
        self.btn_process.configure(state="normal", text="SPRÓBUJ PONOWNIE")
        messagebox.showerror("Błąd RMBG", f"Nie udało się usunąć tła.\n{error_msg}")

    def save_and_close(self, result_pil):
        self.callback(result_pil, self.image_path)
        self.destroy()
        
        self.callback = callback

        ctk.CTkLabel(self, text="Użycie RMBG-2.0", font=("Arial", 18, "bold")).pack(pady=10)
        ctk.CTkLabel(self, text="Model briaai/RMBG-2.0 jest udostępniony na licencji Non-Commercial.", wraplength=450).pack(pady=5)
        ctk.CTkLabel(self, text="Oznacza to, że możesz go używać wyłącznie do celów niekomercyjnych.", wraplength=450).pack(pady=5)
        ctk.CTkLabel(self, text="Jeśli zamierzasz używać go komercyjnie, skontaktuj się z Bria AI.", wraplength=450, text_color="red").pack(pady=5)
        
        ctk.CTkLabel(self, text="Więcej informacji o licencji:").pack(pady=5)
        self.license_link = ctk.CTkLabel(self, text="https://huggingface.co/briaai/RMBG-2.0", text_color="blue", cursor="hand2")
        self.license_link.pack()
        self.license_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://huggingface.co/briaai/RMBG-2.0"))

        ctk.CTkButton(self, text="Akceptuję warunki i rozumiem ograniczenia", command=self.accept, fg_color="green", hover_color="darkgreen").pack(pady=15)
        ctk.CTkButton(self, text="Nie akceptuję / Anuluj", command=self.reject, fg_color="gray", hover_color="darkgray").pack(pady=5)

        self.grab_set()

    def accept(self):
        self.callback(True)
        self.destroy()

    def reject(self):
        self.callback(False)
        self.destroy()

class DeleteDialog(ctk.CTkToplevel):
    def __init__(self, parent, paths, callback):
        super().__init__(parent)
        self.title("Usuwanie plików")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.paths = paths
        self.callback = callback
        
        count = len(paths)
        msg = f"Wybrano {count} plików.\nCzy na pewno chcesz usunąć je z dysku?"
        if count == 1:
            msg = f"Plik: {os.path.basename(paths[0])}\nCzy na pewno chcesz usunąć go z dysku?"

        ctk.CTkLabel(self, text="OSTRZEŻENIE", text_color="red", font=("Arial", 16, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text=msg, font=("Arial", 12), wraplength=350).pack(pady=10)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10, fill="x", padx=40)

        ctk.CTkButton(btn_frame, text="PRZENIEŚ DO /tmp (Kosz)", command=self.move_to_tmp, fg_color=ME_YELLOW, text_color="black", hover_color=ME_YELLOW_HOVER).pack(fill="x", pady=5)
        ctk.CTkButton(btn_frame, text="USUŃ TRWALE (Nieodwracalne)", command=self.delete_permanently, fg_color="#cc0000", hover_color="#aa0000").pack(fill="x", pady=5)
        ctk.CTkButton(btn_frame, text="Anuluj", command=self.destroy, fg_color="gray").pack(fill="x", pady=5)

        self.grab_set()

    def move_to_tmp(self):
        self.callback("tmp", self.paths)
        self.destroy()

    def delete_permanently(self):
        self.callback("perm", self.paths)
        self.destroy()



class ConfigManager:
    def __init__(self, filename="config.ini"):
        self.config = configparser.ConfigParser()
        self.filename = filename
        if os.path.exists(self.filename):
            self.config.read(self.filename)
        else:
            # Ustaw wartości domyślne, jeśli plik nie istnieje
            self.config['RMBG'] = {'license_accepted': 'no'}
            self.save()

    def get(self, section, option, default=None):
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))
        self.save()

    def save(self):
        with open(self.filename, 'w') as configfile:
            self.config.write(configfile)

class AsystentApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager() # Inicjalizacja menedżera konfiguracji
        self.title("asystentPIM v1.0.8") 
        self.geometry("1350x895")
        self.set_icon()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.file_list = []
        self.last_dir = self.config_manager.get('SETTINGS', 'last_dir', os.path.expanduser("~"))
        
        self.overwrite_var = ctk.BooleanVar(value=False) 
        
        self.current_preview_path = None
        self.preview_image_ref = None 
        
        self.view_vars = {} 
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
        system_platform = platform.system()
        if system_platform == "Windows":
            bin_name = "realesrgan-ncnn-vulkan.exe"
        elif system_platform == "Darwin":
            bin_name = "realesrgan-ncnn-vulkan-mac"
        else:
            bin_name = "realesrgan-ncnn-vulkan"

        self.ai_tool_path = shutil.which(bin_name)
        if self.ai_tool_path: return True
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_bin = os.path.join(script_dir, bin_name)
        if os.path.exists(script_bin) and os.access(script_bin, os.X_OK):
            self.ai_tool_path = script_bin
            return True

        local_bin = os.path.abspath(bin_name)
        if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
            self.ai_tool_path = local_bin
            return True

        if hasattr(sys, '_MEIPASS'):
            temp_bin = os.path.join(sys._MEIPASS, bin_name)
            if os.path.exists(temp_bin): 
                try: os.chmod(temp_bin, 0o755)
                except: pass
                self.ai_tool_path = temp_bin
                return True
                
        return False

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=ME_BLACK)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(50, weight=1)

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

        self.btn_border_lr = ctk.CTkButton(self.sidebar, text="PASEK 5px L+P", command=self.add_border_lr_5px, **btn_me)
        self.btn_border_lr.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_border_lr'] = {'widget': self.btn_border_lr, 'row': current_row}
        current_row += 1

        self.btn_border_tb = ctk.CTkButton(self.sidebar, text="PASEK 5px G+D", command=self.add_border_tb_5px, **btn_me)
        self.btn_border_tb.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_border_tb'] = {'widget': self.btn_border_tb, 'row': current_row}
        current_row += 1

        self.btn_crop = ctk.CTkButton(self.sidebar, text="KADRUJ (AUTO)", command=self.auto_crop, **btn_me)
        self.btn_crop.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_crop'] = {'widget': self.btn_crop, 'row': current_row}
        current_row += 1

        self.btn_crop_select = ctk.CTkButton(self.sidebar, text="KADRUJ (ZAZNACZENIE)", command=self.open_crop_editor, **btn_me)
        self.btn_crop_select.grid(row=current_row, column=0, padx=15, pady=5)
        self.sidebar_widgets['btn_crop_select'] = {'widget': self.btn_crop_select, 'row': current_row}
        self.btn_crop_select.grid_remove() # Domyślnie ukryty
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
        self.context_menu.add_command(label="Edytuj obraz (domyślnie)", command=self.edit_default_image)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Inpainting (Usuń obiekt)", command=self.open_inpainting)
        self.context_menu.add_command(label="Usuń tło (RMBG-2.0)", command=self.open_rembg)
        self.context_menu.add_command(label="Sprawdź obraz (Inspekcja)", command=self.check_image)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Zapisz zaznaczone do ZIP", command=self.save_to_zip)
        self.context_menu.add_command(label="Zapisz zaznaczone do 7z", command=self.save_to_7z)
        self.context_menu.add_command(label="Usuń z listy", command=self.remove_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ USUŃ Z DYSKU", command=self.delete_from_disk_dialog)
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
            # Odczytaj stan z configu, jeśli istnieje, w przeciwnym razie użyj default
            saved_state = self.config_manager.get('VIEW', widget_key)
            if saved_state is not None:
                is_visible = saved_state == 'True'
            else:
                is_visible = default
            
            var = tk.BooleanVar(value=is_visible)
            self.view_vars[label] = var
            widget_data = self.sidebar_widgets.get(widget_key)
            
            if widget_data:
                widget = widget_data['widget']
                
                # Funkcja opakowująca zapis do configu
                def on_toggle(w=widget, v=var, k=widget_key):
                    self.toggle_widget(w, v, k)
                    self.config_manager.set('VIEW', k, str(v.get()))

                view_menu.add_checkbutton(label=label, variable=var, command=on_toggle)
                
                if not is_visible:
                    widget.grid_remove()
            else:
                view_menu.add_checkbutton(label=label, variable=var, state='disabled',
                                          command=lambda: print(f"Widget {widget_key} not found"))
            return var

        add_toggle("Nagłówek aplikacji", 'lbl_app_title')
        add_toggle("Media Expert Logo", 'lbl_me_expert', default=False)

        view_menu.add_command(label="--- Główne ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b1')
        add_toggle("Dodaj obrazy", 'btn_add')
        add_toggle("Wyczyść listę", 'btn_clear')
        add_toggle("Usuń zaznaczenie", 'btn_remove')
        add_toggle("Kolejność (przyciski)", 'frame_order') 
        
        view_menu.add_separator()
        view_menu.add_command(label="--- Ustawienia ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b2', default=False) # Domyślnie ukryte
        add_toggle("Jakość JPG (slider)", 'frame_quality', default=False) # Domyślnie ukryte
        add_toggle("Nadpisz pliki (checkbox)", 'chk_overwrite', default=False) # Domyślnie ukryte
        
        view_menu.add_separator()
        view_menu.add_command(label="--- Konwersja ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b3')
        add_toggle("Konwertuj do JPG", 'btn_jpg')
        add_toggle("Konwertuj do WebP", 'btn_webp', default=False)
        
        view_menu.add_separator()
        view_menu.add_command(label="--- Edycja i Skalowanie ---", state='disabled')
        add_toggle("Etykieta sekcji", 'lbl_b4')
        add_toggle("Dodaj białe tło", 'btn_white_bg')
        add_toggle("Dodaj ramkę", 'btn_border')
        add_toggle("Kadruj (Auto)", 'btn_crop')
        add_toggle("Kadruj (Zaznaczenie)", 'btn_crop_select', default=False)
        add_toggle("Zwiększ do 500px", 'btn_upscale')
        add_toggle("Dopasuj 3000x3600", 'btn_downscale')
        add_toggle("Dodaj ramkę 5px", 'btn_border')
        add_toggle("Pasek 5px L+P", 'btn_border_lr')
        add_toggle("Pasek 5px G+D", 'btn_border_tb')
        
        if hasattr(self, 'btn_ai'): # Sprawdź czy AI jest dostępne, zanim dodasz do menu
            view_menu.add_separator()
            add_toggle("AI Smart Upscale", 'btn_ai')
            add_toggle("AI Settings", 'frame_ai_settings') # Ukrywa label i entry AI

        # Menu Experimental
        experimental_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Experimental", menu=experimental_menu)
        experimental_menu.add_command(label="Inpainting (AI)", command=self.open_inpainting)
        experimental_menu.add_command(label="Usuń tło (RMBG-2.0 Lokalnie)", command=self.open_rembg)

        # Menu Export
        export_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Export", menu=export_menu)
        export_menu.add_command(label="Eksportuj do PDF (Zaznaczone)", command=self.export_to_pdf)
        export_menu.add_command(label="Eksportuj do JPG (Zaznaczone)", command=self.export_to_jpg)

        # Menu About
        about_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="About", menu=about_menu)
        about_menu.add_command(label="O programie", command=self.show_about)
        about_menu.add_command(label="Media Expert", command=self.open_me_website)

    def show_about(self):
        msg = "asystentPIM v1.0.8\n\n"
        msg += "Technologie:\n"
        msg += "• Python & CustomTkinter\n"
        msg += "• RMBG-2.0 (Bria AI) - Usuwanie tła\n"
        msg += "• Stable Diffusion - Inpainting (Wymaga A1111)\n"
        msg += "• Real-ESRGAN - Upscaling\n"
        msg += "• GIMP Integration\n\n"
        msg += "Dla: Media Expert"
        messagebox.showinfo("O programie", msg)

    def toggle_widget(self, widget, var, widget_key):
        if var.get():
            widget.grid() 
        else:
            widget.grid_remove() 

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

    def export_to_pdf(self):
        # Pobierz zaznaczone (zafajkowane) pliki
        items_to_process = []
        for item in self.tree.get_children():
            vals = self.tree.item(item)['values']
            if vals[0] == "☑":
                path = self.tree.item(item)['tags'][0]
                if os.path.exists(path):
                    items_to_process.append(path)
        
        if not items_to_process:
            messagebox.showinfo("Info", "Zaznacz pliki (checkboxem ☑) do eksportu.")
            return

        # Wybierz miejsce zapisu
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Zapisz jako PDF",
            initialdir=self.last_dir,
            initialfile=f"Export_{len(items_to_process)}_files.pdf"
        )
        
        if not save_path: return

        try:
            images = []
            # Pierwszy obraz
            first_image = Image.open(items_to_process[0]).convert("RGB")
            
            # Reszta obrazów
            for path in items_to_process[1:]:
                img = Image.open(path).convert("RGB")
                images.append(img)
            
            # Zapisz
            first_image.save(save_path, save_all=True, append_images=images)
            messagebox.showinfo("Sukces", f"Pomyślnie utworzono plik PDF:\n{os.path.basename(save_path)}")
            
        except Exception as e:
            messagebox.showerror("Błąd PDF", f"Nie udało się utworzyć PDF.\n{e}")

    def export_to_jpg(self):
        items_to_process = []
        for item in self.tree.get_children():
            vals = self.tree.item(item)['values']
            if vals[0] == "☑":
                path = self.tree.item(item)['tags'][0]
                if os.path.exists(path):
                    items_to_process.append(path)
        
        if not items_to_process:
            messagebox.showinfo("Info", "Zaznacz pliki do eksportu.")
            return

        export_dir = filedialog.askdirectory(title="Wybierz folder docelowy")
        if not export_dir: return

        count = 0
        for path in items_to_process:
            try:
                name = os.path.splitext(os.path.basename(path))[0]
                save_path = os.path.join(export_dir, f"{name}.jpg")
                
                img = Image.open(path).convert("RGB")
                img.save(save_path, "JPEG", quality=95)
                count += 1
            except Exception as e:
                print(f"Błąd eksportu JPG {path}: {e}")
        
        # Opcjonalnie: messagebox.showinfo("Sukces", f"Wyeksportowano {count} plików do JPG.")

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
                    messagebox.showerror("Błąd", f"Nie udało się uruchomić GIMP na macOS: {e}\nSprawdź, czy GIMP jest zainstalowany.")
            elif platform.system() == "Linux":
                # Sprawdź Flatpak
                if shutil.which("flatpak"):
                    try:
                        # Próba uruchomienia wersji Flatpak
                        subprocess.Popen(['flatpak', 'run', 'org.gimp.GIMP', path])
                        return
                    except: pass
                
                # Standardowy GIMP
                try:
                    subprocess.Popen(['gimp', path])
                except FileNotFoundError:
                    messagebox.showerror("Błąd", "Nie znaleziono programu GIMP (ani standardowego, ani Flatpak).")
            else:
                # Windows
                try:
                    subprocess.Popen(['gimp', path])
                except FileNotFoundError:
                    messagebox.showerror("Błąd", "Nie znaleziono programu GIMP. Upewnij się, że jest w PATH.")
                    try: subprocess.Popen(['flatpak', 'run', 'org.gimp.GIMP', path])
                    except: messagebox.showerror("Błąd", "Nie znaleziono programu GIMP (Linux/Windows).")

    def edit_default_image(self): 
        sel = self.tree.selection()
        if sel:
            path = self.tree.item(sel[0])['tags'][0]
            if not os.path.exists(path): return
            self.open_path(path) 

    def open_inpainting(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showwarning("Info", "Wybierz obraz do edycji.")
            return
        
        path = self.tree.item(sel[0])['tags'][0]
        if not os.path.exists(path): return

        # Otwórz edytor inpaintingu
        editor = InpaintingEditor(self, path, self.after_inpainting)
        editor.grab_set() # Zablokuj główne okno

    def check_image(self):
        sel = self.tree.selection()
        if not sel: return
        path = self.tree.item(sel[0])['tags'][0]
        if not os.path.exists(path): return
        
        CheckImageDialog(self, path)

    def open_rembg(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showwarning("Info", "Wybierz obraz do edycji.")
            return
        
        path = self.tree.item(sel[0])['tags'][0]
        if not os.path.exists(path): return

        # Otwórz edytor usuwania tła
        editor = RmbgEditor(self, path, self.after_rembg, self.config_manager)
        editor.grab_set()

    def after_rembg(self, result_image, original_path):
        try:
            original_dir = os.path.dirname(original_path)
            filename = os.path.basename(original_path)
            name_root, ext = os.path.splitext(filename)
            
            # Zawsze zapisz jako PNG (bo musi być przezroczystość)
            save_path = os.path.join(original_dir, f"{name_root}_no_bg.png")

            # Zapisz wynik
            result_image.save(save_path, "PNG", optimize=True)
            
            self.status_label.configure(text=f"Tło usunięte: {os.path.basename(save_path)}")
            
            # Sprzątanie pliku tymczasowego
            temp_output = os.path.join(original_dir, "temp_rmbg_result.png")
            if os.path.exists(temp_output):
                try: os.remove(temp_output)
                except: pass

            # ARCHIWIZACJA ORYGINAŁU
            orig_archive_dir = os.path.join(original_dir, "_orig")
            os.makedirs(orig_archive_dir, exist_ok=True)
            archived_path = os.path.join(orig_archive_dir, filename)
            
            # Przenieś oryginał do _orig
            if not os.path.exists(archived_path):
                shutil.move(original_path, archived_path)
            else:
                import time
                ts = int(time.time())
                archived_path = os.path.join(orig_archive_dir, f"{name_root}_{ts}{ext}")
                shutil.move(original_path, archived_path)
            
            # Odśwież listę (usuń oryginał, dodaj wynik)
            # 1. Usuń oryginał z widoku
            for item in self.tree.get_children():
                if self.tree.item(item)['tags'][0] == original_path:
                    self.tree.delete(item)
                    break
            
            # 2. Usuń oryginał z listy plików
            self.file_list = [p for p in self.file_list if p != original_path]

            # 3. Dodaj wynik
            self.file_list.append(save_path)
            new_item_id = self.insert_tree_item(save_path)
            if new_item_id:
                self.tree.selection_set(new_item_id)
                self.tree.see(new_item_id)
            
            self.update_indexes()
            
            # messagebox.showinfo("Sukces", f"Zapisano jako:\n{os.path.basename(save_path)}")

        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def after_inpainting(self, result_image, original_path):
        # Callback po zakończeniu inpaintingu
        try:
            original_dir = os.path.dirname(original_path)
            filename = os.path.basename(original_path)
            name_root, ext = os.path.splitext(filename)
            
            overwrite = self.overwrite_var.get()
            
            if overwrite:
                # Kopia oryginału do _orig
                orig_archive_dir = os.path.join(original_dir, "_orig")
                os.makedirs(orig_archive_dir, exist_ok=True)
                archived_path = os.path.join(orig_archive_dir, filename)
                
                if not os.path.exists(archived_path):
                    shutil.copy2(original_path, archived_path) 
                
                save_path = original_path
            else:
                save_path = os.path.join(original_dir, f"{name_root}_inpainting{ext}")

            # Zapisz wynik
            result_image.save(save_path, quality=100, optimize=True)
            
            self.status_label.configure(text=f"Inpainting zakończony: {os.path.basename(save_path)}")
            
            # Odśwież listę
            if not overwrite:
                self.file_list.append(save_path)
                self.insert_tree_item(save_path)
            else:
                if self.current_preview_path == save_path:
                    self.show_preview(save_path)
            
            self.update_indexes()

        except Exception as e:
            messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać wyniku: {e}")

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

    def save_to_7z(self): 
        selected = self.tree.selection()
        if not selected: return messagebox.showwarning("Info", "Wybierz pliki do spakowania.")
        
        sevenz_path = shutil.which('7z')
        if not sevenz_path:
            messagebox.showerror("Błąd", "Nie znaleziono programu '7z' w systemie.\nUpewnij się, że '7z' (p7zip) jest zainstalowany i dostępny w PATH.")
            return

        target_7z = filedialog.asksaveasfilename(defaultextension=".7z", filetypes=[("Archiwum 7z", "*.7z")], title="Zapisz jako 7z")
        if not target_7z: return

        files_to_compress = [self.tree.item(item)['tags'][0] for item in selected if os.path.exists(self.tree.item(item)['tags'][0])]
        
        try:
            cmd = [sevenz_path, 'a', '-t7z', target_7z] + files_to_compress
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
        files = filedialog.askopenfilenames(
            title="Wybierz obrazy",
            initialdir=self.last_dir,
            filetypes=types
        )
        if files:
            # Zapisz ostatnio wybrany katalog
            self.last_dir = os.path.dirname(files[0])
            self.config_manager.set('SETTINGS', 'last_dir', self.last_dir)
            for file_path in files:
                self.process_added_files([file_path]) # Przenieś to tutaj, żeby było w pętli

    def add_folder(self):
        folder_path = filedialog.askdirectory(
            title="Wybierz folder",
            initialdir=self.last_dir # Użyj ostatnio zapamiętanego katalogu
        )
        if folder_path:
            # Zapisz ostatnio wybrany katalog
            self.last_dir = folder_path
            self.config_manager.set('SETTINGS', 'last_dir', self.last_dir)
            
            # Przetwarzanie plików z folderu
            all_files_in_folder = []
            for root, _, files in os.walk(folder_path):
                for file in files:
                    all_files_in_folder.append(os.path.join(root, file))
            self.process_added_files(all_files_in_folder) # Przetwórz wszystkie pliki naraz

    def remove_selected(self):
        selected_paths = []
        for item in self.tree.selection():
            path = self.tree.item(item)['tags'][0]
            selected_paths.append(path)
            self.tree.delete(item)
        
        # Usuń z self.file_list
        self.file_list = [p for p in self.file_list if p not in selected_paths]

        self.update_indexes()
        self.lbl_preview.configure(image="", text="Wybierz plik")

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
        if not os.path.exists(path): return None # Zwróć None, jeśli ścieżka nie istnieje
        try:
            size = os.path.getsize(path)
            name = os.path.basename(path)
            res = "N/A"
            try:
                with Image.open(path) as img: res = f"{img.width}x{img.height} px"
            except:
                pass
            # Dodano "☑" jako wartość dla kolumny "chk"
            item_id = self.tree.insert("", "end", values=("☑", "", name, self.format_bytes(size), res, "📂"), tags=[path])
            return item_id # Zwróć ID nowo dodanego elementu
        except Exception as e:
            print(f"Błąd podczas wstawiania elementu: {e}")
            return None

    def remove_selected(self):
        selected_paths = []
        for item in self.tree.selection():
            path = self.tree.item(item)['tags'][0]
            selected_paths.append(path)
            self.tree.delete(item)
        
        # Usuń z self.file_list
        self.file_list = [p for p in self.file_list if p not in selected_paths]

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
            w, h = i.size
            bg = Image.new("RGB", (w + 10, h + 10), "white") # Biała ramka 5px
            bg.paste(i, (5, 5))
            return bg
        self.process_images("Ramka 5px", f)

    def add_border_lr_5px(self):
        def f(i):
            w, h = i.size
            new_w = w + 10  # 5px z lewej, 5px z prawej
            bg = Image.new("RGB", (new_w, h), "white")
            bg.paste(i, (5, 0)) # Wklej obraz na środku (x=5, y=0)
            return bg
        self.process_images("Pasek L+P 5px", f)

    def add_border_tb_5px(self):
        def f(i):
            w, h = i.size
            new_h = h + 10  # 5px z góry, 5px z dołu
            bg = Image.new("RGB", (w, new_h), "white")
            bg.paste(i, (0, 5)) # Wklej obraz na środku (x=0, y=5)
            return bg
        self.process_images("Pasek G+D 5px", f)

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
                    bg = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255)) # Białe tło
                    # Wklejamy na środek
                    x = (new_w - w) // 2
                    y = (new_h - h) // 2
                    bg.paste(i, (x, y), i) # Używamy i jako maski dla przezroczystości
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

    def open_crop_editor(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showwarning("Info", "Wybierz obraz do kadrowania.")
            return
        
        path = self.tree.item(sel[0])['tags'][0]
        if not os.path.exists(path): return

        # Otwórz edytor
        editor = CropEditor(self, path, self.after_crop)
        editor.wait_visibility() # Poczekaj aż okno się pojawi
        editor.grab_set()

    def after_crop(self, result_image, original_path):
        try:
            original_dir = os.path.dirname(original_path)
            filename = os.path.basename(original_path)
            name_root, ext = os.path.splitext(filename)
            
            # Jeśli nadpisywanie włączone
            overwrite = self.overwrite_var.get()
            
            if overwrite:
                save_path = original_path
            else:
                save_path = os.path.join(original_dir, f"{name_root}_crop{ext}")

            # Zapisz wynik
            result_image.save(save_path, quality=100, optimize=True)
            
            self.status_label.configure(text=f"Wykadrowano: {os.path.basename(save_path)}")
            
            if not overwrite:
                # ARCHIWIZACJA ORYGINAŁU
                orig_archive_dir = os.path.join(original_dir, "_orig")
                os.makedirs(orig_archive_dir, exist_ok=True)
                archived_path = os.path.join(orig_archive_dir, filename)
                
                if not os.path.exists(archived_path):
                    shutil.move(original_path, archived_path)
                else:
                    import time
                    ts = int(time.time())
                    archived_path = os.path.join(orig_archive_dir, f"{name_root}_{ts}{ext}")
                    shutil.move(original_path, archived_path)

                # Odśwież listę (usuń oryginał, dodaj wynik)
                # 1. Usuń oryginał z widoku
                for item in self.tree.get_children():
                    if self.tree.item(item)['tags'][0] == original_path:
                        self.tree.delete(item)
                        break
                
                # 2. Usuń oryginał z listy plików
                self.file_list = [p for p in self.file_list if p != original_path]

                # 3. Dodaj wynik
                self.file_list.append(save_path)
                new_item_id = self.insert_tree_item(save_path)
                if new_item_id:
                    self.tree.selection_set(new_item_id)
                    self.tree.see(new_item_id)
            else:
                # Odśwież info o pliku (rozmiar się zmienił)
                self.update_indexes() 

            # messagebox.showinfo("Sukces", f"Zapisano jako:\n{os.path.basename(save_path)}")

        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def delete_from_disk_dialog(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showinfo("Info", "Zaznacz pliki do usunięcia.")
            return
        
        paths = [self.tree.item(i)['tags'][0] for i in sel]
        DeleteDialog(self, paths, self.perform_deletion)

    def perform_deletion(self, mode, paths):
        deleted_count = 0
        
        for path in paths:
            try:
                if not os.path.exists(path): continue
                
                if mode == "perm":
                    os.remove(path)
                elif mode == "tmp":
                    dirname = os.path.dirname(path)
                    tmp_dir = os.path.join(dirname, "tmp")
                    os.makedirs(tmp_dir, exist_ok=True)
                    fname = os.path.basename(path)
                    dest = os.path.join(tmp_dir, fname)
                    
                    # Unikaj nadpisywania w tmp
                    base, ext = os.path.splitext(fname)
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(tmp_dir, f"{base}_{counter}{ext}")
                        counter += 1
                        
                    shutil.move(path, dest)
                
                deleted_count += 1
            except Exception as e:
                print(f"Błąd usuwania {path}: {e}")

        # Odśwież listę (usuń zaznaczone z widoku)
        if deleted_count > 0:
            self.remove_selected()
            # Opcjonalnie: messagebox.showinfo("Sukces", f"Usunięto/Przeniesiono {deleted_count} plików.")

if __name__ == "__main__":
    app = AsystentApp()
    app.mainloop()
