INSERT INTO uygulama_ayarlari (anahtar, deger, aciklama)
VALUES
    ('cds_calisma_saati', '18:00', 'CDS birincil gonderim saati (Europe/Istanbul, HH:MM)'),
    ('cds_gunluk_gonderim_sayisi', '1', 'CDS gunluk Telegram gonderim sayisi'),
    ('cds_gonderim_saatleri', '18:00', 'CDS gonderim saatleri (virgulle ayrilmis, HH:MM)'),
    ('cds_bugun_gonderim_tarihi', '', 'CDS bugunku gonderim sayaci tarihi (Europe/Istanbul)'),
    ('cds_bugun_gonderilen_saatler', '[]', 'CDS bugun gonderilen saatler (JSON liste)')
ON CONFLICT (anahtar) DO NOTHING;
