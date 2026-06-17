INSERT INTO uygulama_ayarlari (anahtar, deger, aciklama)
VALUES
    ('brand_worker_aktif', '1', 'Brand worker calissin mi (1/0)'),
    ('brand_telegram_chat_id', '', 'Brand Telegram chat ID'),
    ('brand_telegram_topic_id', '', 'Brand Telegram topic ID (grup icin)'),
    ('brand_calisma_saati', '09:00', 'Brand birincil gonderim saati (Europe/Istanbul)'),
    ('brand_gunluk_gonderim_sayisi', '1', 'Brand gunluk calisma zamani sayisi'),
    ('brand_gonderim_saatleri', '09:00', 'Brand gonderim saatleri (virgulle ayrilmis)'),
    ('brand_bugun_gonderim_tarihi', '', 'Brand bugunku zaman sayaci tarihi'),
    ('brand_bugun_gonderilen_saatler', '[]', 'Brand bugun gonderilen saatler (JSON)'),
    ('brand_rapor_yili', '2026', 'Brandirectory Turkiye rapor yili'),
    ('brand_sirket_gonderim_sayisi', '1', 'Her calismada gonderilecek sirket sayisi'),
    ('brand_gunluk_sirket_limiti', '5', 'Bir gunde en fazla gonderilecek sirket sayisi'),
    ('brand_bugun_sirket_tarihi', '', 'Brand sirket gunluk sayac tarihi'),
    ('brand_bugun_sirket_sayisi', '0', 'Brand bugun gonderilen sirket sayisi'),
    ('brand_rapor_publication_id', '', 'Aktif Brandirectory publication ID'),
    ('brand_overview_gonderildi', '0', 'Rapor ozeti gonderildi mi (publication ID)'),
    ('brand_son_gonderilen_rank', '0', 'Son gonderilen sirket siralamasi'),
    ('son_brand_kontrol_zamani', '', 'Son basarili Brand kontrolu (UTC ISO)')
ON CONFLICT (anahtar) DO NOTHING;
