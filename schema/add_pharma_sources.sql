-- Pharma news RSS feeds. Run in Supabase SQL Editor if not using migrations.
-- Adds Fierce Pharma and ET Pharma; dashboard shows them under the "Pharma" tab.

INSERT INTO sources (name, feed_url, base_url, category) VALUES
    ('Fierce Pharma', 'https://rss.app/feeds/ecpIY4Jdts048Kzn.xml', 'https://www.fiercepharma.com/', 'Pharma'),
    ('ET Pharma', 'https://rss.app/feeds/gOzflD5oMN4P9Eor.xml', 'https://pharma.economictimes.indiatimes.com/', 'Pharma')
ON CONFLICT (feed_url) DO UPDATE SET
    name = EXCLUDED.name,
    base_url = EXCLUDED.base_url,
    category = EXCLUDED.category;
