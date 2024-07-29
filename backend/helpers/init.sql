-- Drop existing tables if they exist
DROP TABLE IF EXISTS wait_times CASCADE;
DROP TABLE IF EXISTS hospitals CASCADE;
DROP TABLE IF EXISTS hospital_pages CASCADE;
DROP TABLE IF EXISTS hospital_wait_times CASCADE;
DROP TABLE IF EXISTS script_metadata CASCADE;
DROP TABLE IF EXISTS hospital_page_links CASCADE;

-- Create hospitals table
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    facility_id VARCHAR(50) UNIQUE NOT NULL,
    website_id VARCHAR(50) UNIQUE,
    facility_name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    county VARCHAR(100),
    phone_number VARCHAR(20),
    hospital_type VARCHAR(100),
    hospital_ownership VARCHAR(100),
    emergency_services BOOLEAN,
    has_live_wait_time BOOLEAN DEFAULT FALSE,
    has_wait_time_data BOOLEAN DEFAULT FALSE,
    latitude FLOAT,
    longitude FLOAT,
    er_volume VARCHAR(50),
    wait_time INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Create wait_times table
CREATE TABLE wait_times (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER REFERENCES hospitals(id),
    wait_time INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create hospital_pages table
CREATE TABLE hospital_pages (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    hospital_num INTEGER
);

-- Create hospital_wait_times table (for backwards compatibility)
CREATE TABLE hospital_wait_times (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255) NOT NULL,
    hospital_address VARCHAR(255),
    wait_time VARCHAR(255),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create script_metadata table
CREATE TABLE script_metadata (
    script_name VARCHAR(255) PRIMARY KEY,
    last_run TIMESTAMP WITH TIME ZONE
);

-- Create hospital_page_links table
CREATE TABLE hospital_page_links (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER REFERENCES hospitals(id),
    hospital_page_id INTEGER REFERENCES hospital_pages(id),
    UNIQUE (hospital_id, hospital_page_id)
);

-- Create indexes for faster queries
CREATE INDEX idx_hospitals_lat_long ON hospitals (latitude, longitude);
CREATE INDEX idx_wait_times_hospital_timestamp ON wait_times (hospital_id, timestamp);
CREATE INDEX idx_hospital_page_links_hospital_id ON hospital_page_links (hospital_id);
CREATE INDEX idx_hospital_page_links_hospital_page_id ON hospital_page_links (hospital_page_id);

-- Function to match hospitals with hospital pages
CREATE OR REPLACE FUNCTION match_hospitals() RETURNS void AS $$
DECLARE
    page_record RECORD;
    hospital_record RECORD;
BEGIN
    FOR page_record IN SELECT id, hospital_name FROM hospital_pages LOOP
        FOR hospital_record IN 
            SELECT id, facility_name 
            FROM hospitals 
            WHERE facility_name ILIKE '%' || page_record.hospital_name || '%'
               OR page_record.hospital_name ILIKE '%' || facility_name || '%'
        LOOP
            INSERT INTO hospital_page_links (hospital_id, hospital_page_id)
            VALUES (hospital_record.id, page_record.id)
            ON CONFLICT DO NOTHING;

            -- Update the has_wait_time_data flag
            UPDATE hospitals SET has_wait_time_data = TRUE WHERE id = hospital_record.id;
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Initialize script_metadata
INSERT INTO script_metadata (script_name, last_run) 
VALUES ('main_script', TO_TIMESTAMP('1970-01-01 00:00:00', 'YYYY-MM-DD HH24:MI:SS'))
ON CONFLICT (script_name) DO NOTHING;