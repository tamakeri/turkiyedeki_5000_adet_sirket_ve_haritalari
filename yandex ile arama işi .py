import requests
import pandas as pd
import time
import os

# --- AYARLAR ---
INPUT_FILE = r"// şirketlerin listesi after groq processed_data.csv"
OUTPUT_FILE = "final_company_atlas_FULL.csv"
API_KEY = ""
GUNLUK_SINIR = 7000

def yandex_search(company_name):
    """Yandex üzerinden şirket bilgilerini çeker (Direkt Lowercase)."""
    # Büyük harf sorununu çözmek için direkt küçük harfe çeviriyoruz
    search_text = str(company_name).replace('İ', 'i').replace('I', 'ı').lower()
    
    url = "https://search-maps.yandex.ru/v1/"
    params = {
        "text": search_text, 
        "lang": "tr_TR", 
        "apikey": API_KEY, 
        "type": "biz", 
        "results": 1
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 403: 
            return "LIMIT_STOP"
        if response.status_code != 200: 
            return None
        
        data = response.json()
        if not data.get('features'): 
            return None
        
        feature = data['features'][0]
        props = feature.get('properties', {}).get('CompanyMetaData', {})
        geom = feature.get('geometry', {}).get('coordinates', [None, None])
        
        return {
            "resmi_ad": props.get('name'),
            "gercek_sektor": ", ".join([c['name'] for c in props.get('Categories', [])]),
            "telefon": props.get('Phones', [{}])[0].get('formatted', 'Yok'),
            "web": props.get('url', 'Yok'),
            "lat": geom[1],
            "lon": geom[0]
        }
    except:
        return None

# --- ÇALIŞTIRMA VE KAYIT MANTIĞI ---

if os.path.exists(OUTPUT_FILE):
    df = pd.read_csv(OUTPUT_FILE)
    print(f"🔄 Mevcut dosya bulundu, kalınan yerden devam ediliyor...")
else:
    df = pd.read_csv(INPUT_FILE)
    for col in ['resmi_ad', 'gercek_sektor', 'telefon', 'web', 'lat', 'lon']:
        if col not in df.columns: 
            df[col] = None
    print("🆕 Yeni işlem başlatılıyor...")

islenen_bugun = 0
toplam_satir = len(df)

print(f"🚀 Toplam: {toplam_satir} | Bugün Hedef: {GUNLUK_SINIR} | Durdurmak için: Ctrl+C")

try:
    for index, row in df.iterrows():
        # Günlük sınır kontrolü
        if islenen_bugun >= GUNLUK_SINIR:
            print(f"\n✅ Bugünlük {GUNLUK_SINIR} sorgu sınırına ulaşıldı.")
            break

        # Daha önce işlenen satırları atla
        if pd.notnull(row['lat']):
            continue
        
        sirket_ismi = row['sirket_adi']
        res = yandex_search(sirket_ismi)
        
        if res == "LIMIT_STOP":
            print("\n🛑 Yandex API limiti doldu (HTTP 403).")
            break
            
        if res:
            df.at[index, 'resmi_ad'] = res['resmi_ad']
            df.at[index, 'gercek_sektor'] = res['gercek_sektor']
            df.at[index, 'telefon'] = res['telefon']
            df.at[index, 'web'] = res['web']
            df.at[index, 'lat'] = res['lat']
            df.at[index, 'lon'] = res['lon']
            print(f"[{index+1}/{toplam_satir}] ✅ {res['resmi_ad']}")
        else:
            # Bulunamayanları 0.0 yaparak işaretle (Tekrar aratmasın)
            df.at[index, 'lat'] = 0.0 
            print(f"[{index+1}/{toplam_satir}] ❌ Bulunamadı: {sirket_ismi}")

        islenen_bugun += 1
        
        # Her 25 işlemde bir yedekle
        if islenen_bugun % 25 == 0:
            df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            print(f"💾 {islenen_bugun} veri yedeklendi...")

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\n🛑 İşlem kullanıcı tarafından durduruldu (Ctrl+C).")

finally:
    # Her ihtimalde veriyi kaydet (Hata veya manuel durdurma)
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"🏁 Son durum kaydedildi. Toplam ilerleme: {df['lat'].notnull().sum()} / {toplam_satir}")