-- GramBiz AI — Production PostGIS query reference.
-- These queries are the production-optimized equivalents of the portable
-- haversine logic in apps/api/app/geo.py. They use PostGIS for efficient,
-- index-backed radius/distance on the Postgres side.
--
-- NOTE: apps/api/app/geo.py now serves these ST_DWithin queries directly and
-- automatically, whenever PostgreSQL supports PostGIS AND the table carries
-- the `geom` geography column (bootstrap: python -m scripts.db.postgis). The
-- SQL below remains the canonical reference for the exact query shapes.

-- Enable extensions (docker-compose does this already):
-- CREATE EXTENSION IF NOT EXISTS postgis;
-- CREATE EXTENSION IF NOT EXISTS vector;  -- for pgvector RAG

-- Spatial index on businesses (add after backfill):
-- CREATE INDEX idx_businesses_geom ON businesses USING GIST (geom);

-- If using a geography column approach, add a geography column:
-- ALTER TABLE businesses ADD COLUMN geom geography(Point,4326);
-- UPDATE businesses SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography;

-- 1) businesses within radius (exact, ellipsoidal via geography)
-- SELECT id, name, category_code,
--        ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000 AS distance_km
-- FROM businesses
-- WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_km * 1000)
-- ORDER BY distance_km;

-- 2) competitor count within 5/10 km
-- SELECT COUNT(*) FROM businesses
-- WHERE category_code = :category
--   AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 5000);

-- 3) business density: count per cell / per 1000 households (join population)
-- SELECT b.category_code, COUNT(*) AS n
-- FROM businesses b
-- WHERE ST_DWithin(b.geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 10000)
-- GROUP BY b.category_code;

-- 4) distance to nearest infrastructure (market / transport)
-- SELECT kind, MIN(ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)/1000) AS nearest_km
-- FROM infrastructure_points
-- WHERE kind IN ('market','transport')
-- AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 20000)
-- GROUP BY kind;
