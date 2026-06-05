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
    ('worker_aktif', '1', 'Worker calissin mi (1/0)')
ON CONFLICT (anahtar) DO NOTHING;

CREATE INDEX IF NOT EXISTS ix_gonderilen_yayin_tarihi
    ON gonderilen_bildirimler (gonderim_tarihi DESC);

CREATE INDEX IF NOT EXISTS ix_log_tarih
    ON islem_loglari (olusturma_tarihi DESC);

CREATE INDEX IF NOT EXISTS ix_filtre_aktif
    ON filtre_kurallari (aktif) WHERE aktif = TRUE;
