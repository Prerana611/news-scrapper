-- Add image_url column to articles table for storing article thumbnail images.
-- Run in Supabase SQL Editor.

ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;

CREATE INDEX IF NOT EXISTS idx_articles_image_url ON articles(image_url) WHERE image_url IS NOT NULL;
