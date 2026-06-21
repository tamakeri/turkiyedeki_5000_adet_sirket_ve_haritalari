import os
import json
import time
import csv
from groq import Groq

# 1. AYARLARI OKU
def config_yukle():
    conf = {}
    try:
        with open("config.txt", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    conf[k.strip()] = v.strip()
        return conf
    except FileNotFoundError:
        print("HATA: config.txt bulunamadı!")
        exit()

config = config_yukle()
client = Groq(api_key=config.get("GROQ_API_KEY"))

def analiz_et(sirket_adi):
    prompt = f"""
    Kurum: {sirket_adi}
    SADECE bu JSON formatında yanıt ver:
    {{
        "sektor": "Şirketin faaliyet alanı",
        "tip": "Kamu veya Özel"
    }}
    """
    try:
        completion = client.chat.completions.create(
            model=config.get("GROQ_MODEL_NAME"),
            messages=[
                {"role": "system", "content": "Sadece saf JSON çıktısı veren bir asistansın."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"  (!) Hata ({sirket_adi}): {e}")
        return None

def main():
    input_path = "../data/sirketler.txt"
    output_path = "../data/processed_data.csv"
    
    if not os.path.exists(input_path):
        print(f"HATA: {input_path} bulunamadı!")
        return

    # İşlenecek tüm şirketleri oku
    with open(input_path, "r", encoding="utf-8") as f:
        tum_sirketler = [line.strip() for line in f if line.strip()]

    # GEÇMİŞ KONTROLÜ (Hangi şirketler zaten işlenmiş?)
    islenmis_sirketler = set()
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                islenmis_sirketler.add(row["sirket_adi"])

    # Sadece işlenmemiş olanları filtrele
    islenmemis_liste = [s for s in tum_sirketler if s not in islenmis_sirketler]
    
    atlanan_sayisi = len(tum_sirketler) - len(islenmemis_liste)
    print(f"--- ANALİZ BAŞLADI ---")
    print(f"Toplam: {len(tum_sirketler)} | Zaten İşlenmiş: {atlanan_sayisi} | Kalan: {len(islenmemis_liste)}")

    if not islenmemis_liste:
        print("Tüm şirketler zaten işlenmiş. İşlem sonlandırılıyor.")
        return

    # CSV Dosyasını 'a' (append) modunda açıyoruz
    file_exists = os.path.isfile(output_path)
    with open(output_path, "a", encoding="utf-8-sig", newline="") as csvfile:
        fieldnames = ["sirket_adi", "sektor", "tip"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()

        for i, sirket in enumerate(islenmemis_liste, 1):
            print(f"[{i}/{len(islenmemis_liste)}] İşleniyor: {sirket}")
            
            analiz = analiz_et(sirket)
            if analiz:
                writer.writerow({
                    "sirket_adi": sirket,
                    "sektor": analiz.get("sektor", "Bilinmiyor"),
                    "tip": analiz.get("tip", "Bilinmiyor")
                })
                csvfile.flush()
                os.fsync(csvfile.fileno()) 
            
            # Rate limit koruyucu: 30 RPM için 2.1 saniye
            time.sleep(2.1)

    print(f"\nBitti! Kalan {len(islenmemis_liste)} şirket başarıyla eklendi.")

if __name__ == "__main__":
    main()