INSERT INTO uygulama_ayarlari (anahtar, deger, aciklama)
VALUES
    ('brand_son_snapshot', '', 'Brandirectory son siralama snapshot (JSON)'),
    ('son_brand_kontrol_tarihi', '', 'Son Brand kontrol tarihi (Europe/Istanbul YYYY-MM-DD)')
ON CONFLICT (anahtar) DO NOTHING;
