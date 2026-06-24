# KAP Haberleri Cloud

KAP bildirimlerini filtreleyip Telegram'a gonderen bulut surumu. CDS ve Brand worker'lari da ayni zamanlayici ile calisir.

| Bilesen | Gorev |
|---------|-------|
| **Panel** (`app.py`) | Filtreler, CDS/Brand saatleri, manuel test |
| **GitHub Actions** (`kap_worker.yml`) | KAP + CDS + Brand (her 5 dk) |
| **Supabase PostgreSQL** | Ayarlar, loglar, gonderim kayitlari |
| **cron-job.org** | `kap_worker.yml` workflow dispatch (guvenilir tetikleyici) |

Yerel SQL Server surumu: `C:\Kap Haberleri`

## Mimari

```
cron-job.org (5 dk)
    -> kap_worker.yml
        -> worker_once.py       (KAP bildirimleri)
        -> cds_worker_once.py   (panel saati gelince CDS)
        -> brand_worker_once.py (panel saati gelince Brand)
```

CDS ve Brand her turda calisir ama **sadece panelde yazdiginiz saat penceresinde** Telegram'a gonderir. Yeni cron job gerekmez.

## 1. Supabase PostgreSQL (ucretsiz)

1. [supabase.com](https://supabase.com) → hesap acin → **New project**
2. **Region:** `Frankfurt (eu-central-1)` (Turkiye'ye yakin)
3. Database sifresini kaydedin (bir daha gosterilmez)
4. Proje hazir olunca: **Project Settings → Database → Connection string**
5. Asagidaki iki URI'den birini kullanin:

| Kullanim | Supabase'de secim | Not |
|----------|-------------------|-----|
| Panel + worker (`.env`, GitHub Secret) | **Session pooler**, port `5432` | Onerilen |
| Ilk sema kurulumu (`init_db`) | **Direct connection**, port `5432` | DDL icin guvenilir |

Ornek (Session pooler):

```
postgresql://postgres.PROJECT_REF:SIFRE@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
```

6. Semayi uygulayin:

```powershell
cd "C:\Kap Haberleri Cloud"
copy .env.example .env
# .env icine DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID yazin
pip install -r requirements.txt
python scripts/init_db.py
```

`init_db` hata verirse `.env` icinde gecici olarak **Direct connection** URI kullanin; sema kurulduktan sonra Session pooler URI'ye donun.

**Neon'dan gecis:** Eski Neon verisi tasima gerektirir. Neon kapaliysa panelden filtreleri ve CDS/Brand ayarlarini yeniden girin.

## 2. Yerel panel

```powershell
cd "C:\Kap Haberleri Cloud"
streamlit run app.py
```

Veya `run_panel.bat` dosyasini calistirin.

Panel `.env` dosyasindan okur. CDS/Brand calisma saatlerini **Ayarlar** sayfasindan kaydedin; ayarlar Supabase DB'ye yazilir.

## 3. GitHub

**Repository Secrets** (Settings → Secrets → Actions):

| Secret | Deger |
|--------|-------|
| `DATABASE_URL` | Supabase Session pooler connection string |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Varsayilan chat ID |

Actions sekmesinden **KAP Worker** workflow'unu `Run workflow` ile test edin. Calismada KAP, CDS ve Brand adimlarini gormelisiniz.

### Otomatik worker (5 dakika)

GitHub'in yerlesik `schedule` tetikleyicisi bazi repolarda guvenilir calismaz. **Onerilen:** [cron-job.org](https://cron-job.org) ile mevcut **KAP Worker** job'unu her 5 dakikada tetikleyin.

1. GitHub → **Developer settings** → **Personal access tokens** (fine-grained)
2. Repository: `kap-haberleri-cloud`, izin: **Actions: Read and write**
3. [cron-job.org](https://console.cron-job.org) → cron job:
   - **URL:** `https://api.github.com/repos/dogukanancar/kap-haberleri-cloud/actions/workflows/kap_worker.yml/dispatches`
   - **Schedule:** every 5 minutes
   - **Method:** POST
   - **Headers:**
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer GITHUB_TOKEN_BURAYA`
     - `X-GitHub-Api-Version: 2022-11-28`
   - **Body:** `{"ref":"main"}`
4. **Test run** → Actions'ta **KAP Worker** baslamali

Yedek: repodaki **KAP Worker Zamanlayici** workflow'u GitHub schedule ile ana worker'i tetiklemeyi dener.

Yerel manuel tetikleme:

```powershell
$env:GITHUB_TOKEN = "ghp_..."
.\scripts\trigger_github_worker.ps1
```

## 4. Streamlit Cloud (istege bagli)

Paneli bulutta calistirmak isterseniz [share.streamlit.io](https://share.streamlit.io) uzerinden deploy edin. Secrets: `.streamlit/secrets.toml.example` ile ayni anahtarlar.

## Notlar

- Supabase free: 500 MB DB, 1 hafta hareketsizlikte pause (cron job acik tutar)
- KAP, CDS ve Brand **ayri worker kodlari** kullanir; tetikleme tek workflow (`kap_worker.yml`) uzerinden yapilir
- Panelde **KAP worker aktif** kapaliysa KAP gondermez; CDS/Brand icin kendi aktif kutulari vardir
- CDS/Brand saatleri panelden degistiginde git push gerekmez; ayar DB'de tutulur
- Ucretsiz GitHub Actions: public repo icin genis limit; private repo icin aylik kota vardir
