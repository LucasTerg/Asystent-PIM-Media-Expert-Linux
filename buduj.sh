#!/bin/bash

# Nazwa kontenera distrobox (zgodna z distrobox.ini)
CONTAINER_NAME="asystent-dev"

# Jeśli kontener 'asystent-dev' nie istnieje, spróbuj użyć 'arch' (Twojego obecnego)
if ! distrobox list | grep -q "$CONTAINER_NAME"; then
    echo "Kontener '$CONTAINER_NAME' nie znaleziony. Próba użycia kontenera 'arch'..."
    CONTAINER_NAME="arch"
fi

echo "Rozpoczynam budowanie w kontenerze: $CONTAINER_NAME..."

# 1. Budowanie narzędzia RMBG (jako FOLDER --onedir, aby uniknąć problemów z dekompresją w /tmp)
echo "Budowanie narzędzia RMBG-2.0 (rmbg_tool)..."
distrobox-enter -n "$CONTAINER_NAME" -- .venv_rmbg/bin/pyinstaller --noconfirm --onedir --console \
    --name "rmbg_tool" \
    --hidden-import=torch \
    --hidden-import=torchvision \
    --copy-metadata=torch \
    --copy-metadata=tqdm \
    --copy-metadata=regex \
    --copy-metadata=requests \
    --copy-metadata=packaging \
    --copy-metadata=filelock \
    --copy-metadata=numpy \
    --collect-all transformers \
    --collect-all torch \
    --collect-all timm \
    --collect-all kornia \
    local_rmbg.py

# 2. Budowanie głównej aplikacji (AsystentMediaExpert)
echo "Budowanie Asystenta..."
distrobox-enter -n "$CONTAINER_NAME" -- pyinstaller --noconfirm --onefile --windowed \
    --name "AsystentMediaExpert" \
    --collect-all customtkinter \
    --hidden-import='PIL._tkinter_finder' \
    --add-binary "realesrgan-ncnn-vulkan:." \
    --add-data "models/realesr-animevideov3-x2.bin:models" \
    --add-data "models/realesr-animevideov3-x2.param:models" \
    main.py

echo "Zakończono. Pliki wynikowe znajdują się w folderze dist/"
echo "Struktura:"
echo "  dist/AsystentMediaExpert (plik)"
echo "  dist/rmbg_tool/ (folder z narzędziem AI)"
