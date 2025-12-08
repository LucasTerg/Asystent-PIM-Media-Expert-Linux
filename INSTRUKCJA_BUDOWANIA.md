# Instrukcja budowania i uruchamiania Asystenta PIM (LinuxPort)

Dokument ten opisuje procedurę uruchamiania i kompilowania aplikacji na systemie Linux (np. SteamOS / Steam Deck), wykorzystując kontener **Arch Linux** w **Distrobox**. Jest to konieczne ze względu na specyficzne zależności systemowe (np. `tk`, kodeki obrazów), które mogą być trudne do zainstalowania bezpośrednio na systemie hosta.

## 1. Automatyczna konfiguracja środowiska (Zalecane)

Projekt posiada plik konfiguracyjny `distrobox.ini`, który automatycznie tworzy kontener z systemem Arch Linux i instaluje wszystkie wymagane biblioteki.

Będąc w folderze `LinuxPort`, wykonaj:
```bash
distrobox assemble create --file distrobox.ini
```

Po zakończeniu operacji wejdź do gotowego środowiska:
```bash
distrobox enter asystent-dev
```

## 2. Ręczna instalacja (Opcjonalnie)

Jeśli wolisz ręcznie skonfigurować środowisko (bez pliku .ini):

**Krok A: Pakiety systemowe (Arch)**
```bash
sudo pacman -S --noconfirm python python-pip tk
```

**Krok B: Biblioteki Python**
```bash
python -m pip install -r requirements.txt --break-system-packages
```


## 3. Uruchamianie wersji roboczej

Aby przetestować program bez kompilacji (szybkie zmiany):
```bash
python LinuxPort/main.py
```

## 4. Budowanie pliku wykonywalnego (ELF)

Aby stworzyć jeden, samodzielny plik, który można uruchomić bez wchodzenia do kontenera i bez instalowania Pythona, używamy `PyInstaller`.

Będąc w katalogu głównym projektu (wewnątrz distrobox), wykonaj:

```bash
# Upewnij się, że jesteś w katalogu LinuxPort
# cd LinuxPort

pyinstaller --noconfirm --onefile --windowed --name "AsystentMediaExpert" \
 --collect-all customtkinter --hidden-import='PIL._tkinter_finder' \
 --add-binary "realesrgan-ncnn-vulkan:." \
 --add-data "models/realesr-animevideov3-x2.bin:models" \
 --add-data "models/realesr-animevideov3-x2.param:models" \
 main.py
```

### Gdzie jest plik?
Gotowy program znajdziesz w folderze:
`dist/AsystentMediaExpert`

Możesz go stamtąd skopiować w dowolne miejsce na dysku.

## 5. Rozwiązywanie problemów

- **Błąd `ModuleNotFoundError: No module named ...`**: Oznacza, że nie wszedłeś do distroboxa lub nie wykonałeś Kroku 2B.
- **Ostrzeżenia `ldd: brak uprawnień do wykonywania...`**: Podczas budowania są normalne i można je zignorować.
- **Problem z `kdialog`**: Wersja obecna używa wbudowanego `tkinter`, więc nie wymaga `kdialog` w systemie, ale wymaga pakietu `tk` zainstalowanego w Kroku 2A.
