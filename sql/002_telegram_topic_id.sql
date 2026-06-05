ALTER TABLE filtre_kurallari
    ADD COLUMN IF NOT EXISTS telegram_topic_id VARCHAR(20);
