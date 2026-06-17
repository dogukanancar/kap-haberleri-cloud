INSERT INTO uygulama_ayarlari (anahtar, deger, aciklama)
VALUES
    ('son_brand_gonderim_tarihi', '', 'Son Brand tablo gonderim tarihi (Europe/Istanbul YYYY-MM-DD)')
ON CONFLICT (anahtar) DO NOTHING;
