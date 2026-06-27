-- KAP Haberleri Cloud - PostgreSQL semasi (idempotent, sifirdan kurulum)
-- Calistirma: python scripts/init_db.py

CREATE TABLE IF NOT EXISTS filtre_kurallari (
    id                SERIAL PRIMARY KEY,
    kural_adi         VARCHAR(100) NOT NULL,
    aktif             BOOLEAN NOT NULL DEFAULT TRUE,
    sirket_kodlari    TEXT,
    konu_oid_listesi  TEXT,
    anahtar_kelimeler TEXT,
    haric_kelimeler   TEXT,
    bildirim_sinifi   VARCHAR(20),
    telegram_chat_id  VARCHAR(50) NOT NULL,
    telegram_topic_id VARCHAR(20),
    olusturma_tarihi  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    guncelleme_tarihi TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS gonderilen_bildirimler (
    id                BIGSERIAL PRIMARY KEY,
    disclosure_index  BIGINT NOT NULL,
    sirket_kodu       VARCHAR(20),
    sirket_adi        VARCHAR(250),
    konu              VARCHAR(500),
    baslik            VARCHAR(1000),
    yayin_tarihi      TIMESTAMPTZ NOT NULL,
    kap_url           VARCHAR(500) NOT NULL,
    telegram_chat_id  VARCHAR(50) NOT NULL,
    filtre_kural_id   INTEGER REFERENCES filtre_kurallari(id),
    gonderim_tarihi   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (disclosure_index, telegram_chat_id)
);

CREATE TABLE IF NOT EXISTS islem_loglari (
    id               BIGSERIAL PRIMARY KEY,
    seviye           VARCHAR(20) NOT NULL,
    kaynak           VARCHAR(50) NOT NULL,
    mesaj            TEXT NOT NULL,
    detay            TEXT,
    olusturma_tarihi TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS uygulama_ayarlari (
    anahtar           VARCHAR(100) PRIMARY KEY,
    deger             TEXT NOT NULL,
    aciklama          VARCHAR(250),
    guncelleme_tarihi TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO uygulama_ayarlari (anahtar, deger, aciklama)
VALUES
    ('polling_araligi_saniye', '300', 'GitHub Actions kontrol araligi (bilgi amacli)'),
    ('son_kontrol_zamani', '', 'Son basarili KAP kontrolu (UTC ISO)'),
    ('worker_aktif', '1', 'Worker calissin mi (1/0)'),
    ('cds_worker_aktif', '1', 'CDS worker calissin mi (1/0)'),
    ('cds_telegram_chat_id', '', 'CDS Telegram chat ID'),
    ('cds_telegram_topic_id', '', 'CDS Telegram topic ID (grup icin)'),
    ('son_cds_gonderim_tarihi', '', 'Son CDS gonderim tarihi (Europe/Istanbul YYYY-MM-DD)'),
    ('son_cds_degeri', '', 'Son gonderilen CDS degeri (bp)'),
    ('son_cds_kontrol_zamani', '', 'Son basarili CDS kontrolu (UTC ISO)'),
    ('cds_calisma_saati', '18:00', 'CDS birincil gonderim saati (Europe/Istanbul, HH:MM)'),
    ('cds_gonderim_saatleri', '18:00', 'CDS gonderim saatleri (virgulle ayrilmis, HH:MM)'),
    ('cds_bugun_gonderim_tarihi', '', 'CDS bugunku gonderim sayaci tarihi (Europe/Istanbul)'),
    ('cds_bugun_gonderilen_saatler', '[]', 'CDS bugun gonderilen saatler (JSON liste)'),
    ('brand_worker_aktif', '1', 'Brand worker calissin mi (1/0)'),
    ('brand_telegram_chat_id', '', 'Brand Telegram chat ID'),
    ('brand_telegram_topic_id', '', 'Brand Telegram topic ID (grup icin)'),
    ('brand_calisma_saati', '09:00', 'Brand birincil kontrol saati (Europe/Istanbul)'),
    ('brand_gonderim_saatleri', '09:00', 'Brand kontrol saatleri (virgulle ayrilmis)'),
    ('brand_bugun_gonderim_tarihi', '', 'Brand bugunku zaman sayaci tarihi'),
    ('brand_bugun_gonderilen_saatler', '[]', 'Brand bugun gonderilen saatler (JSON)'),
    ('brand_rapor_yili', '2026', 'Brandirectory Turkiye rapor yili'),
    ('son_brand_kontrol_zamani', '', 'Son basarili Brand kontrolu (UTC ISO)'),
    ('son_brand_gonderim_tarihi', '', 'Son Brand uyari gonderim tarihi (Europe/Istanbul)'),
    ('brand_son_snapshot', '', 'Brandirectory son siralama snapshot (JSON)'),
    ('son_brand_kontrol_tarihi', '', 'Son Brand kontrol tarihi (Europe/Istanbul YYYY-MM-DD)')
ON CONFLICT (anahtar) DO NOTHING;

CREATE INDEX IF NOT EXISTS ix_gonderilen_gonderim_tarihi
    ON gonderilen_bildirimler (gonderim_tarihi DESC);

CREATE INDEX IF NOT EXISTS ix_log_tarih
    ON islem_loglari (olusturma_tarihi DESC);

CREATE INDEX IF NOT EXISTS ix_filtre_aktif
    ON filtre_kurallari (aktif) WHERE aktif = TRUE;

DROP INDEX IF EXISTS ix_gonderilen_yayin_tarihi;

ALTER TABLE filtre_kurallari
    ADD COLUMN IF NOT EXISTS telegram_topic_id VARCHAR(20);
