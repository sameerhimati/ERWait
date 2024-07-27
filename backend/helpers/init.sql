-- Drop existing tables if they exist
DROP TABLE IF EXISTS hospitals CASCADE;
DROP TABLE IF EXISTS wait_times CASCADE;

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
    latitude FLOAT,
    longitude FLOAT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create wait_times table
CREATE TABLE wait_times (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER REFERENCES hospitals(id),
    wait_time INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster geographical queries
CREATE INDEX idx_hospitals_location ON hospitals USING GIST (
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
);

-- Create index for faster wait time queries
CREATE INDEX idx_wait_times_hospital_timestamp ON wait_times (hospital_id, timestamp);

-- Create index for website_id lookups
CREATE INDEX idx_hospitals_website_id ON hospitals(website_id);