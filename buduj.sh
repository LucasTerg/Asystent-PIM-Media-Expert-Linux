#!/bin/bash

# Nazwa kontenera distrobox (zgodna z distrobox.ini)
CONTAINER_NAME="asystent-dev"

# Jeśli kontener 'asystent-dev' nie istnieje, spróbuj użyć 'arch' (Twojego obecnego)
if ! distrobox list | grep -q "$CONTAINER_NAME"; then
    echo "Kontener '$CONTAINER_NAME' nie znaleziony. Próba użycia kontenera 'arch'..."
    CONTAINER_NAME="arch"
fi

echo "Rozpoczynam budowanie w kontenerze: $CONTAINER_NAME..."

# Uruchomienie budowania wewnątrz kontenera
# Zakładamy, że skrypt jest uruchamiany z katalogu LinuxPort
distrobox-enter -n "$CONTAINER_NAME" -- pyinstaller --noconfirm --onefile --windowed \
    --name "AsystentMediaExpert" \
    --collect-all customtkinter \
    --hidden-import='PIL._tkinter_finder' \
    --add-binary "realesrgan-ncnn-vulkan:." \
    --add-data "models/realesr-animevideov3-x2.bin:models" \
    --add-data "models/realesr-animevideov3-x2.param:models" \
    main.py

echo "Zakończono. Plik wynikowy znajduje się w folderze dist/"
