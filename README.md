# KAP Haberleri Cloud

KAP bildirimlerini filtreleyip Telegram'a gonderen bulut surumu.

- **Streamlit Cloud** → web panel (`app.py`)
- **GitHub Actions** → worker (`worker_once.py`, her 5 dakika)
- **Neon PostgreSQL** → veritabani

Yerel SQL Server surumu: `C:\Kap Haberleri`

## 1. Neon PostgreSQL

1. [neon.tech](https://neon.tech) uzerinde ucretsiz proje olusturun
2. Connection string kopyalayin (`postgresql://...?sslmode=require`)
3. Semayi uygulayin:

```powershell
cd "C:\Kap Haberleri Cloud"
copy .env.example .env
# .env icine DATABASE_URL yazin
pip install -r requirements.txt
python scripts/init_db.py
```

## 2. GitHub

```powershell
cd "C:\Kap Haberleri Cloud"
git init
git add .
git commit -m "KAP Haberleri cloud surumu"
git remote add origin https://github.com/KULLANICI/kap-haberleri-cloud.git
git push -u origin main
```

**Repository Secrets** (Settings → Secrets → Actions):

| Secret | Deger |
|--------|-------|
| `DATABASE_URL` | Neon connection string |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHAT_ID` | Varsayilan chat ID |

Actions sekmesinden **KAP Worker** workflow'unu `Run workflow` ile test edin.

## 3. Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → New app
2. GitHub reposunu baglayin
3. Main file: `app.py`
4. **Secrets** ekleyin (`.streamlit/secrets.toml.example` ile ayni anahtarlar)
5. Deploy

## Notlar

- Worker panelden degil, **GitHub Actions** ile calisir (5 dk)
- Panelde **Worker aktif** kapaliysa Actions da calismaz
- Ucretsiz GitHub Actions: public repo icin genis limit; private repo icin aylik kota var
