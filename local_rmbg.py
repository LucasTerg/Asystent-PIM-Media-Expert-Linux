import sys
import os
from PIL import Image
import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

def remove_background(input_path, output_path):
    print(f"Inicjalizacja RMBG-2.0 dla: {input_path}")
    
    # Wykrywanie urządzenia (CUDA lub CPU)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Używane urządzenie: {device.upper()}")

    try:
        # Ładowanie modelu
        print("Ładowanie modelu briaai/RMBG-2.0...")
        model = AutoModelForImageSegmentation.from_pretrained('briaai/RMBG-2.0', trust_remote_code=True)
        model.to(device)
        model.eval()

        # Przygotowanie obrazu
        image_size = (1024, 1024)
        transform_image = transforms.Compose([
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        image = Image.open(input_path).convert("RGB")
        original_size = image.size
        
        input_images = transform_image(image).unsqueeze(0).to(device)

        # Predykcja
        print("Przetwarzanie obrazu...")
        with torch.no_grad():
            preds = model(input_images)[-1].sigmoid().cpu()
        
        pred = preds[0].squeeze()
        pred_pil = transforms.ToPILImage()(pred)
        
        # Skalowanie maski do oryginalnego rozmiaru
        mask = pred_pil.resize(original_size)
        
        # Nakładanie maski
        image.putalpha(mask)

        # Zapis
        image.save(output_path, "PNG")
        print(f"Zapisano wynik: {output_path}")
        
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Użycie: python local_rmbg.py <input_image> <output_image>")
        sys.exit(1)
        
    input_img = sys.argv[1]
    output_img = sys.argv[2]
    
    remove_background(input_img, output_img)
