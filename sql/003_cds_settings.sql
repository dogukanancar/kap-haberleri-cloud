INSERT INTO uygulama_ayarlari (anahtar, deger, aciklama)
VALUES
    ('cds_worker_aktif', '1', 'CDS worker calissin mi (1/0)'),
    ('cds_telegram_chat_id', '', 'CDS Telegram chat ID'),
    ('cds_telegram_topic_id', '', 'CDS Telegram topic ID (grup icin)'),
    ('son_cds_gonderim_tarihi', '', 'Son CDS gonderim tarihi (Europe/Istanbul YYYY-MM-DD)'),
    ('son_cds_degeri', '', 'Son gonderilen CDS degeri (bp)'),
    ('son_cds_kontrol_zamani', '', 'Son basarili CDS kontrolu (UTC ISO)')
ON CONFLICT (anahtar) DO NOTHING;
