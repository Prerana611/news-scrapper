-- Run in Supabase SQL Editor to get tabs: All, News, Sport, Business, Technology, Health.
-- Adds category to sources and adds BBC feeds for each section (https://www.bbc.com/).

ALTER TABLE sources ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'General';

-- General news sources → "News" tab
UPDATE sources SET category = 'News' WHERE name IN ('BBC News', 'CNN', 'Google News');
UPDATE sources SET category = 'News' WHERE category = 'General' OR category = 'World';

-- Tech → "Technology" tab (existing Reuters)
UPDATE sources SET category = 'Technology' WHERE name = 'Reuters';

-- BBC section feeds (same structure as https://www.bbc.com/ nav: Sport, Business, Technology, Health)
INSERT INTO sources (name, feed_url, base_url, category) VALUES
    ('BBC Sport', 'https://feeds.bbci.co.uk/sport/rss.xml', 'https://www.bbc.com/sport', 'Sport'),
    ('BBC Business', 'https://feeds.bbci.co.uk/news/business/rss.xml', 'https://www.bbc.com/news/business', 'Business'),
    ('BBC Technology', 'https://feeds.bbci.co.uk/news/technology/rss.xml', 'https://www.bbc.com/news/technology', 'Technology'),
    ('BBC Health', 'https://feeds.bbci.co.uk/news/health/rss.xml', 'https://www.bbc.com/news/health', 'Health')
ON CONFLICT (feed_url) DO UPDATE SET category = EXCLUDED.category, name = EXCLUDED.name, base_url = EXCLUDED.base_url;
