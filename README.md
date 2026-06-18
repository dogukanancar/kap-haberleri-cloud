# KAP Haberleri Cloud

KAP bildirimlerini filtreleyip Telegram'a gonderen bulut surumu. CDS ve Brand worker'lari da ayni zamanlayici ile calisir.

| Bilesen | Gorev |
|---------|-------|
| **Panel** (`app.py`) | Filtreler, CDS/Brand saatleri, manuel test |
| **GitHub Actions** (`kap_worker.yml`) | KAP + CDS + Brand (her 5 dk) |
| **Neon PostgreSQL** | Ayarlar, loglar, gonderim kayitlari |
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

## 1. Neon PostgreSQL

1. [neon.tech](https://neon.tech) uzerinde ucretsiz proje olusturun
2. Connection string kopyalayin (`postgresql://...?sslmode=require`)
3. Semayi uygulayin:

```powershell
cd "C:\Kap Haberleri Cloud"
copy .env.example .env
# .env icine DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID yazin
pip install -r requirements.txt
python scripts/init_db.py
```

## 2. Yerel panel

```powershell
cd "C:\Kap Haberleri Cloud"
streamlit run app.py
```

Veya `run_panel.bat` dosyasini calistirin.

Panel `.env` dosyasindan okur. CDS/Brand calisma saatlerini **Ayarlar** sayfasindan kaydedin; ayarlar Neon DB'ye yazilir.

## 3. GitHub

**Repository Secrets** (Settings -> Secrets -> Actions):

| Secret | Deger |
|--------|-------|
| `DATABASE_URL` | Neon connection string |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Varsayilan chat ID |

Actions sekmesinden **KAP Worker** workflow'unu `Run workflow` ile test edin. Calismada KAP, CDS ve Brand adimlarini gormelisiniz.

### Otomatik worker (5 dakika)

GitHub'in yerlesik `schedule` tetikleyicisi bazi repolarda guvenilir calismaz. **Onerilen:** [cron-job.org](https://cron-job.org) ile mevcut **KAP Worker** job'unu her 5 dakikada tetikleyin.

1. GitHub -> **Developer settings** -> **Personal access tokens** (fine-grained)
2. Repository: `kap-haberleri-cloud`, izin: **Actions: Read and write**
3. [cron-job.org](https://console.cron-job.org) -> cron job:
   - **URL:** `https://api.github.com/repos/dogukanancar/kap-haberleri-cloud/actions/workflows/kap_worker.yml/dispatches`
   - **Schedule:** every 5 minutes
   - **Method:** POST
   - **Headers:**
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer GITHUB_TOKEN_BURAYA`
     - `X-GitHub-Api-Version: 2022-11-28`
   - **Body:** `{"ref":"main"}`
4. **Test run** -> Actions'ta **KAP Worker** baslamali

Yedek: repodaki **KAP Worker Zamanlayici** workflow'u GitHub schedule ile ana worker'i tetiklemeyi dener.

Yerel manuel tetikleme:

```powershell
$env:GITHUB_TOKEN = "ghp_..."
.\scripts\trigger_github_worker.ps1
```

## 4. Streamlit Cloud (istege bagli)

Paneli bulutta calistirmak isterseniz [share.streamlit.io](https://share.streamlit.io) uzerinden deploy edin. Secrets: `.streamlit/secrets.toml.example` ile ayni anahtarlar.

## Notlar

- KAP, CDS ve Brand **ayri worker kodlari** kullanir; tetikleme tek workflow (`kap_worker.yml`) uzerinden yapilir
- Panelde **KAP worker aktif** kapaliysa KAP gondermez; CDS/Brand icin kendi aktif kutulari vardir
- CDS/Brand saatleri panelden degistiginde git push gerekmez; ayar DB'de tutulur
- Ucretsiz GitHub Actions: public repo icin genis limit; private repo icin aylik kota vardir
