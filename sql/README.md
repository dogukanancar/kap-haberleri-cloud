# PostgreSQL semasi (Supabase)

Tek dosyada tum sema: `001_schema.sql`. Idempotent — tekrar calistirmak guvenlidir.

## Kurulum

```powershell
cd "C:\Kap Haberleri Cloud"
copy .env.example .env
# DATABASE_URL doldur
pip install -r requirements.txt
python scripts/init_db.py
python scripts/check_db.py
```

Tam kurulum (seed + migrate): `.\scripts\setup_supabase.ps1`

## Tablolar

| Tablo | Aciklama |
|-------|----------|
| `filtre_kurallari` | Telegram filtre kurallari |
| `gonderilen_bildirimler` | Gonderilmis KAP bildirimleri |
| `islem_loglari` | Uygulama ve worker loglari |
| `uygulama_ayarlari` | Key-value ayar deposu |

## uygulama_ayarlari anahtarlari

Masaustu surumle ayni anahtar seti (PostgreSQL syntax):

| Grup | Anahtarlar |
|------|------------|
| KAP | `worker_aktif`, `polling_araligi_saniye`, `son_kontrol_zamani` |
| CDS | `cds_worker_aktif`, `cds_gonderim_saatleri`, `cds_calisma_saati`, `cds_telegram_*`, `son_cds_*`, `cds_bugun_*` |
| Brand | `brand_worker_aktif`, `brand_gonderim_saatleri`, `brand_rapor_yili`, `brand_son_snapshot`, `son_brand_*`, `brand_bugun_*` |

Tam liste `001_schema.sql` icindeki `INSERT` ifadesindedir.

## Indexler

- `ix_gonderilen_gonderim_tarihi` — `gonderilen_bildirimler(gonderim_tarihi DESC)`
- `ix_log_tarih` — `islem_loglari(olusturma_tarihi DESC)`
- `ix_filtre_aktif` — `filtre_kurallari(aktif) WHERE aktif = TRUE`

Eski kurulumlarda `ix_gonderilen_yayin_tarihi` varsa script otomatik kaldirir.

Masaustu surumu (SQL Server): `C:\Kap Haberleri\sql\`
