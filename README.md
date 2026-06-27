# KAP Haberleri Cloud

KAP bildirimlerini filtreleyip Telegram'a gonderen **bulut** surumu. CDS ve Brand worker'lari GitHub Actions ile calisir.

Masaustu surumu (SQL Server): `C:\Kap Haberleri`

| Bilesen | Gorev |
|---------|-------|
| **Panel** (`app.py`) | Filtreler, CDS/Brand saatleri, DB bakim, manuel test |
| **GitHub Actions** (`kap_worker.yml`) | KAP + CDS + Brand (~5 dk) |
| **Supabase PostgreSQL** | Ayarlar, loglar, gonderim kayitlari |
| **cron-job.org** | Workflow dispatch (onerilen tetikleyici) |

## Mimari

```
cron-job.org (5 dk)
    -> kap_worker.yml
        -> worker_once.py
        -> cds_worker_once.py
        -> brand_worker_once.py

Panel (Streamlit) -> Supabase PostgreSQL
```

CDS ve Brand her turda calisir; Telegram'a yalnizca paneldeki **saat penceresinde** (15 dk) gonderir.

## Proje yapisi

```
Kap Haberleri Cloud/
├── app.py
├── worker_once.py / cds_worker_once.py / brand_worker_once.py
├── src/                       # Masaustu ile ayni modul yapisi
│   └── db_maintenance.py      # PostgreSQL bakim (VACUUM/ANALYZE)
├── sql/
│   ├── 001_schema.sql         # Tum sema (tek dosya)
│   └── README.md
└── scripts/
    ├── init_db.py             # Sifirdan kurulum
    ├── check_db.py            # Baglanti testi
    ├── setup_supabase.ps1     # Tam kurulum (init + seed + migrate)
    └── ...
```

## Hizli kurulum

```powershell
cd "C:\Kap Haberleri Cloud"
copy .env.example .env
pip install -r requirements.txt
# .env: DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
.\scripts\setup_supabase.ps1
```

`setup_supabase.ps1`: baglanti testi → `init_db` → (varsa) desktop aktarimi → seed → `check_db`

### Manuel sema kurulumu

```powershell
python scripts/init_db.py
python scripts/check_db.py
```

`init_db.py` idempotent: `sql/001_schema.sql` dosyasini uygular (tablolar, indexler, varsayilan ayarlar).

### Supabase baglanti

| Kullanim | Secim |
|----------|-------|
| Panel + worker | Session pooler, port 5432 |
| Ilk `init_db` | Direct connection (sorun olursa pooler) |

Ornek:

```
postgresql://postgres.PROJECT_REF:SIFRE@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
```

Semalar: [`sql/README.md`](sql/README.md)

## Panel sayfalari

| Sayfa | Icerik |
|-------|--------|
| **Dashboard** | Bugun gonderilen, aktif kural, son kontrol |
| **Filtreler** | Kural yonetimi; KAP BIST kodlari |
| **Manuel Kontrol** | KAP cekme ve onizleme |
| **Ayarlar** | CDS/Brand/KAP worker, Telegram test |
| **DB Bakim** | Index sagligi, VACUUM/ANALYZE, Supabase yedek bilgisi, veri temizleme |

## Yardimci scriptler

| Script | Gorev |
|--------|-------|
| `migrate_from_desktop.py` | Desktop SQL Server → Supabase |
| `seed_supabase_settings.py` | Uretim ayarlari + ornek filtre |
| `sync_company_list_from_kap.py` | KAP BIST kodlarini filtreye yazar |
| `check_worker_health.py` | Worker ve planli saat kontrolu |
| `set_github_database_secret.py` | GitHub Actions secret guncelleme |

## GitHub Actions

Secrets: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

```powershell
python scripts/trigger_github_worker.py
# veya trigger_worker.bat
```

Otomatik tetikleme: cron-job.org → `kap_worker.yml` dispatch (5 dk)

## Worker davranisi

| Worker | DB anahtari | Gonderim |
|--------|-------------|----------|
| KAP | `worker_aktif` | Her basarili tur |
| CDS | `cds_worker_aktif` | `cds_gonderim_saatleri` penceresinde |
| Brand | `brand_worker_aktif` | `brand_gonderim_saatleri` penceresinde |

Saat penceresi: planlanan saatten itibaren **15 dakika**; kacirilirsa ayni gun **12 saat catch-up**.

## Notlar

- Supabase free: 500 MB; pause on inactivity (cron job DB'yi canli tutar)
- Tam DB yedegi Supabase panelinden alinir (panelde `.bak` yok)
- Ayar degisikligi git push gerektirmez; ayarlar DB'de
