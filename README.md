# KAP Haberleri Cloud

KAP bildirimlerini filtreleyip Telegram'a gonderen bulut surumu. CDS ve Brand worker'lari ayni zamanlayici ile calisir.

| Bilesen | Gorev |
|---------|-------|
| **Panel** (`app.py`) | Filtreler, CDS/Brand saatleri, manuel test |
| **GitHub Actions** (`kap_worker.yml`) | KAP + CDS + Brand (her ~5 dk) |
| **Supabase PostgreSQL** | Ayarlar, loglar, gonderim kayitlari |
| **cron-job.org** | `kap_worker.yml` workflow dispatch (onerilen tetikleyici) |

Yerel SQL Server surumu: `C:\Kap Haberleri`

## Mimari

```
cron-job.org (5 dk, onerilen)
    -> kap_worker.yml
        -> worker_once.py       (KAP bildirimleri)
        -> cds_worker_once.py   (panel saati gelince CDS)
        -> brand_worker_once.py (panel saati gelince Brand)

Yedek: kap_worker_trigger.yml (GitHub schedule -> workflow_dispatch)
```

CDS ve Brand her turda calisir ama **sadece panelde yazdiginiz saat penceresinde** (15 dk) Telegram'a gonderir. Ayri cron job gerekmez.

**Not:** `kap_worker.yml` adimlari sirali calisir. KAP adimi hata verirse ayni turda CDS/Brand calismaz.

## Hizli kurulum (Supabase)

```powershell
cd "C:\Kap Haberleri Cloud"
copy .env.example .env
# .env: DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
pip install -r requirements.txt
.\scripts\setup_supabase.ps1
```

`setup_supabase.ps1` sirasiyla: `init_db` → (varsa) desktop SQL aktarimi → varsayilan ayar seed → baglanti testi.

`.env` icinde `GITHUB_TOKEN` varsa GitHub Actions secret'lari da guncellenir (`set_github_database_secret.py`).

## 1. Supabase PostgreSQL (ucretsiz)

1. [supabase.com](https://supabase.com) → **New project**
2. **Region:** `Frankfurt (eu-central-1)`
3. Database sifresini kaydedin
4. **Project Settings → Database → Connection string → URI**

| Kullanim | Supabase'de secim | Not |
|----------|-------------------|-----|
| Panel + worker (`.env`, GitHub Secret) | **Session pooler**, port `5432` | Onerilen |
| Ilk sema (`init_db`) | **Direct connection** | Windows'ta IPv6 sorunu olursa pooler kullanin |

Ornek (Session pooler — host'u Connect penceresinden **aynen** kopyalayin; `aws-0` veya `aws-1` olabilir):

```
postgresql://postgres.PROJECT_REF:SIFRE@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
```

Manuel sema:

```powershell
python scripts/init_db.py
python scripts/check_db.py
```

**Neon'dan gecis:** Eski Neon kotasi doluysa veri okunamaz. Filtreleri panelden veya scriptlerle yeniden kurun:

| Script | Gorev |
|--------|-------|
| `scripts/migrate_from_desktop.py` | Desktop SQL Server → Supabase (filtre + ayar) |
| `scripts/seed_supabase_settings.py` | Bilinen CDS/Brand/worker ayarlari + ornek filtre |
| `scripts/sync_company_list_from_kap.py` | KAP BIST sirket kodlarini filtre kuralina yazar |
| `scripts/sync_company_list_from_neon.py` | Neon aciksa sirket listesini Neon'dan ceker |
| `scripts/import_filter_from_neon.py` | Neon'dan tum filtre kurallarini aktarir |
| `scripts/check_worker_health.py` | Son worker/GitHub run yasi ve planli saat kontrolu |

## 2. Yerel panel

```powershell
cd "C:\Kap Haberleri Cloud"
.\run_panel.bat
```

Panel `.env` dosyasindan okur. CDS/Brand saatleri ve worker aktif/pasif **Ayarlar** sayfasindan DB'ye yazilir.

### Filtreler

- **Filtreler** sekmesinde kural olusturun veya duzenleyin
- **KAP'tan tum sirketleri cek** butonu: KAP BIST listesindeki (~780) hisse kodunu virgullu listeye ekler (mevcut kodlar korunur)
- **Kaydet** ile kalici olur

## 3. GitHub Actions

### Repository Secrets

Settings → Secrets → Actions:

| Secret | Deger |
|--------|-------|
| `DATABASE_URL` | Supabase Session pooler URI |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Varsayilan chat ID |

`.env` ile toplu guncelleme (yerel):

```powershell
# .env icinde GITHUB_TOKEN=... (fine-grained PAT)
python scripts/set_github_database_secret.py
```

PAT izinleri (repository `kap-haberleri-cloud`):

| Izin | Seviye |
|------|--------|
| Actions | Read and write |
| **Secrets** | Read and write |
| Contents | Read and write |
| Metadata | Read-only |

**Agent secrets** degil — standart **Secrets** izni gerekir.

### Worker testi

Actions → **KAP Worker** → Run workflow. Basarili run'da KAP, CDS ve Brand adimlari gorunur.

### Otomatik tetikleme (5 dakika)

GitHub yerlesik `schedule` her repoda guvenilir degildir. **Onerilen:** [cron-job.org](https://cron-job.org)

1. GitHub → fine-grained PAT (Actions + **Secrets** Read and write)
2. cron-job.org → POST her 5 dk:
   - **URL:** `https://api.github.com/repos/dogukanancar/kap-haberleri-cloud/actions/workflows/kap_worker.yml/dispatches`
   - **Headers:** `Authorization: Bearer TOKEN`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
   - **Body:** `{"ref":"main"}`

Yedek: repodaki **KAP Worker Zamanlayici** (`kap_worker_trigger.yml`).

Yerel manuel tetikleme:

```powershell
python scripts/trigger_github_worker.py
```

veya `trigger_worker.bat` (PowerShell execution policy sorunu yok).

PowerShell scripti:

```powershell
$env:GITHUB_TOKEN = "github_pat_..."
powershell -ExecutionPolicy Bypass -File .\scripts\trigger_github_worker.ps1
```

## 4. Streamlit Cloud (istege bagli)

[share.streamlit.io](https://share.streamlit.io) — Secrets: `.streamlit/secrets.toml.example` ile ayni anahtarlar.

## Worker davranisi

| Worker | DB anahtari | Ne zaman gonderir |
|--------|-------------|-------------------|
| KAP | `worker_aktif` | Her basarili tur; filtre + dedup |
| CDS | `cds_worker_aktif` | `cds_gonderim_saatleri` penceresinde |
| Brand | `brand_worker_aktif` | `brand_gonderim_saatleri` penceresinde |

Saat penceresi: planlanan saatten itibaren **15 dakika**; kacirilirsa ayni gun icinde **12 saat catch-up** (ilk kacirilan slot).

Saglik kontrolu: `python scripts/check_worker_health.py` — cron durdu mu, worker ne zaman calisti.

## Notlar

- Supabase free: 500 MB DB; 1 hafta hareketsizlikte pause (cron job DB'yi canli tutar)
- KAP, CDS ve Brand **ayri worker kodlari**; tetikleme tek workflow uzerinden
- Panelde saat/ayar degisikligi git push gerektirmez; ayarlar DB'de
- Public repo: GitHub Actions kotasi genis; private repoda aylik limit vardir
