import pandas as pd
import json

def harita_olustur(csv_yolu, cikti_yolu="gelismis_sirket_atlasi.html"):
    print(f"'{csv_yolu}' dosyasi okunuyor...")
    try:
        df = pd.read_csv(csv_yolu)
    except FileNotFoundError:
        print(f"Hata: '{csv_yolu}' dosyasi bulunamadi. Lutfen Python dosyasinin ve CSV dosyasinin ayni klasorde oldugundan emin olun.")
        return

    # Eksik verileri doldurma
    df.fillna({'sirket_adi':'Bilinmiyor', 'sektor':'Bilinmiyor', 'tip':'Bilinmiyor', 
               'gercek_sektor':'Yok', 'telefon':'Yok', 'web':'Yok', 'resmi_ad':'Yok'}, inplace=True)

    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')

    # Koordinati olan ve olmayan sirketleri ayirma
    mask = (df['lat'] != 0.0) & (df['lon'] != 0.0) & df['lat'].notna() & df['lon'].notna()
    koordinatli_df = df[mask].copy()
    koordinatsiz_df = df[~mask].copy()

    koordinatli_json = json.dumps(koordinatli_df.to_dict(orient='records'))
    koordinatsiz_json = json.dumps(koordinatsiz_df.to_dict(orient='records'))
    
    # Acilir liste icin sektorleri hazirlama
    sektorler = sorted([str(s) for s in df['sektor'].unique() if str(s).strip() != 'Bilinmiyor' and str(s).strip() != 'nan'])
    sektor_options = "".join([f'<option value="{s}">{s}</option>' for s in sektorler])

    html_template = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>İnteraktif Şirket Atlası</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    
    <style>
        body, html { height: 100%; margin: 0; padding: 0; overflow: hidden; background-color: #f4f6f9; }
        .navbar { height: 65px; z-index: 1050; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .main-container { height: calc(100vh - 65px); display: flex; }
        #sidebar { width: 350px; background-color: #ffffff; border-right: 1px solid #e0e0e0; display: flex; flex-direction: column; z-index: 1000; box-shadow: 2px 0 10px rgba(0,0,0,0.05); }
        #map { flex-grow: 1; z-index: 1; }
        .sidebar-header { padding: 15px 20px; background-color: #f8f9fa; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; }
        .sidebar-content { flex-grow: 1; overflow-y: auto; padding: 0; }
        .list-group-item { border-left: none; border-right: none; border-radius: 0; cursor: pointer; padding: 15px 20px; border-bottom: 1px solid #f0f0f0; transition: background 0.2s; }
        .list-group-item:hover { background-color: #f1f5f9; }
        .company-details { display: none; font-size: 0.9em; margin-top: 10px; background-color: #f8f9fa; padding: 12px; border-radius: 6px; border: 1px solid #e9ecef; }
        .badge-count { font-size: 1em; padding: 6px 10px; }
        .custom-popup .leaflet-popup-content-wrapper { border-radius: 8px; }
        /* Scrollbar stilleri */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #f1f1f1; }
        ::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #a8a8a8; }
    </style>
</head>
<body>

    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#"><i class="fa-solid fa-map-location-dot me-2"></i>Şirket Atlası</a>
            
            <form class="d-flex flex-grow-1 mx-4" onsubmit="event.preventDefault();">
                <input id="searchInput" class="form-control me-2 shadow-sm" type="search" placeholder="Şirket ismi ara..." aria-label="Search">
                
                <select id="filterType" class="form-select me-2 shadow-sm" style="max-width: 200px;">
                    <option value="">Tüm Tipler (Kamu/Özel)</option>
                    <option value="Kamu">Kamu</option>
                    <option value="Özel">Özel</option>
                </select>
                
                <select id="filterSector" class="form-select shadow-sm" style="max-width: 250px;">
                    <option value="">Tüm Sektörler</option>
                    __SEKTOR_OPTIONS__
                </select>
            </form>
        </div>
    </nav>

    <div class="main-container">
        <div id="sidebar">
            <div class="sidebar-header">
                <h6 class="mb-0 fw-bold text-secondary"><i class="fa-solid fa-location-xmark me-2"></i>Konumsuz Şirketler</h6>
                <span id="unlocatedCount" class="badge bg-danger rounded-pill badge-count shadow-sm">0</span>
            </div>
            <div id="sidebarList" class="sidebar-content">
                <ul class="list-group list-group-flush" id="unlocatedList">
                    </ul>
            </div>
        </div>
        
        <div id="map"></div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>

    <script>
        // Python tarafindan gomulen veriler
        const coordsData = __COORDS_DATA__;
        const noCoordsData = __NO_COORDS_DATA__;

        // Haritayi Baslat
        const map = L.map('map', { zoomControl: false }).setView([38.9637, 35.2433], 6);
        L.control.zoom({ position: 'bottomright' }).addTo(map);
        
        // Klasik OpenStreetMap Teması
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        let markers = L.markerClusterGroup({
            chunkedLoading: true,
            maxClusterRadius: 40,
            spiderfyOnMaxZoom: true
        });
        map.addLayer(markers);

        // Ozel Ikonlar
        const publicIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
        });

        const privateIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
        });

        // Popup İcerigi Olusturucu
        function createPopupContent(company) {
            let webLink = (company.web !== 'Yok' && company.web !== 'NaN' && company.web) 
                ? `<a href="${company.web}" target="_blank" class="btn btn-sm btn-outline-primary mt-3 w-100"><i class="fa-solid fa-link me-1"></i>Web Sitesi</a>` 
                : '';
            return `
                <div style="min-width: 220px;" class="custom-popup">
                    <h6 class="fw-bold mb-1" style="color:#2C3E50;">${company.sirket_adi}</h6>
                    <small class="text-muted d-block mb-2">${company.resmi_ad !== 'Yok' ? company.resmi_ad : ''}</small>
                    <div style="font-size: 13px;">
                        <p class="mb-1"><i class="fa-solid fa-briefcase me-2 text-secondary"></i><strong>${company.sektor}</strong></p>
                        <p class="mb-1"><i class="fa-solid fa-building me-2 text-secondary"></i><span class="badge ${company.tip === 'Kamu' ? 'bg-danger' : 'bg-primary'}">${company.tip}</span></p>
                        <p class="mb-0"><i class="fa-solid fa-phone me-2 text-secondary"></i>${company.telefon}</p>
                    </div>
                    ${webLink}
                </div>
            `;
        }

        // Sol menudeki sirketlerin detaylarini acma/kapama
        window.toggleDetails = function(id) {
            const el = document.getElementById(id);
            const icon = document.getElementById('icon_' + id);
            if (el.style.display === 'block') {
                el.style.display = 'none';
                icon.className = 'fa-solid fa-chevron-down text-muted mt-1';
            } else {
                el.style.display = 'block';
                icon.className = 'fa-solid fa-chevron-up text-primary mt-1';
            }
        };

        // Sol Menuyu Listeleme
        function renderUnlocatedList(data) {
            const listEl = document.getElementById('unlocatedList');
            document.getElementById('unlocatedCount').innerText = data.length;
            listEl.innerHTML = '';

            data.forEach((company, index) => {
                const id = `details_${index}`;
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.innerHTML = `
                    <div onclick="toggleDetails('${id}')" class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1 text-dark" style="font-size: 14px; line-height: 1.3;">${company.sirket_adi}</h6>
                            <span class="badge bg-light text-dark border me-1">${company.sektor}</span>
                            <span class="badge ${company.tip === 'Kamu' ? 'bg-danger' : 'bg-primary'}">${company.tip}</span>
                        </div>
                        <i id="icon_${id}" class="fa-solid fa-chevron-down text-muted mt-1" style="font-size: 12px; padding-left: 10px;"></i>
                    </div>
                    <div id="${id}" class="company-details mt-2 shadow-sm">
                        <div class="mb-1"><strong class="text-secondary">Resmi Ad:</strong> ${company.resmi_ad}</div>
                        <div class="mb-1"><strong class="text-secondary">Gerçek Sektör:</strong> ${company.gercek_sektor}</div>
                        <div class="mb-1"><strong class="text-secondary">Telefon:</strong> ${company.telefon}</div>
                        <div class="mt-2">${(company.web !== 'Yok' && company.web) ? `<a href="${company.web}" target="_blank" class="btn btn-sm btn-outline-secondary w-100"><i class="fa-solid fa-arrow-up-right-from-square me-1"></i>Siteye Git</a>` : '<span class="text-muted" style="font-size:12px;"><i class="fa-solid fa-link-slash me-1"></i>Web sitesi yok</span>'}</div>
                    </div>
                `;
                listEl.appendChild(li);
            });
        }

        // Arama ve Filtreleme Mantigi
        function applyFilters() {
            const searchText = document.getElementById('searchInput').value.toLowerCase();
            const filterType = document.getElementById('filterType').value;
            const filterSector = document.getElementById('filterSector').value;

            // Harita Markerlarini Guncelleme
            markers.clearLayers();
            let markerArray = [];
            
            coordsData.forEach(company => {
                if(searchText && !company.sirket_adi.toLowerCase().includes(searchText)) return;
                if(filterType && company.tip !== filterType) return;
                if(filterSector && company.sektor !== filterSector) return;

                const marker = L.marker([company.lat, company.lon], {
                    icon: company.tip === 'Kamu' ? publicIcon : privateIcon
                });
                marker.bindPopup(createPopupContent(company));
                marker.bindTooltip(company.sirket_adi);
                markerArray.push(marker);
            });
            
            markers.addLayers(markerArray);

            // Sol Listeyi Guncelleme
            const filteredUnlocated = noCoordsData.filter(company => {
                if(searchText && !company.sirket_adi.toLowerCase().includes(searchText)) return false;
                if(filterType && company.tip !== filterType) return false;
                if(filterSector && company.sektor !== filterSector) return false;
                return true;
            });

            renderUnlocatedList(filteredUnlocated);
        }

        // Arama kutusu ve filtreler icin event dinleyicileri
        document.getElementById('searchInput').addEventListener('input', applyFilters);
        document.getElementById('filterType').addEventListener('change', applyFilters);
        document.getElementById('filterSector').addEventListener('change', applyFilters);

        // Sayfa acildiginda listeyi doldur
        applyFilters();

    </script>
</body>
</html>'''

    # Python verilerini HTML icine gomuyoruz
    html_template = html_template.replace('__COORDS_DATA__', koordinatli_json)
    html_template = html_template.replace('__NO_COORDS_DATA__', koordinatsiz_json)
    html_template = html_template.replace('__SEKTOR_OPTIONS__', sektor_options)

    # HTML dosyasini kaydetme
    with open(cikti_yolu, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    print(f"\\nHarika! Arama filtreli, sol panelli ve klasik OpenStreetMap temali harita '{cikti_yolu}' adinda olusturuldu.")

if __name__ == "__main__":
    harita_olustur('final_company_atlas_FULL.csv')