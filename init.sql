-- Drop existing tables if they exist
DROP TABLE IF EXISTS hospital_pages CASCADE;
DROP TABLE IF EXISTS hospital_wait_times CASCADE;

-- Create hospital_pages table
CREATE TABLE hospital_pages (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    hospital_num INTEGER NOT NULL
);

-- Create hospital_wait_times table
CREATE TABLE hospital_wait_times (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255) NOT NULL,
    hospital_address VARCHAR(255),
    wait_time VARCHAR(255),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data into hospital_pages
INSERT INTO hospital_pages (hospital_name, url, hospital_num) VALUES
('Edward Health Elmhurst', 'https://www.eehealth.org/services/emergency/wait-times/', 3),
('Piedmont', 'https://www.piedmont.org/emergency-room-wait-times/emergency-room-wait-times', 21),
('Baptist', 'https://www.baptistonline.org/services/emergency', 18),
('Northern Nevada Sparks', 'https://www.nnmc.com/services/emergency-medicine/er-at-northern-nevada-medical-center', 1),
('Northern Nevada Reno', 'https://www.nnmc.com/services/emergency-medicine/er-at-mccarran-nw', 1),
('Northern Nevada Spanish Springs', 'https://www.nnmc.com/services/emergency-medicine/er-at-spanish-springs', 1),
('Metro Health', 'https://www.metrohealth.org/emergency-room', 4);

-- Create an index on hospital_name in both tables to improve join performance
CREATE INDEX idx_hospital_pages_name ON hospital_pages(hospital_name);
CREATE INDEX idx_hospital_wait_times_name ON hospital_wait_times(hospital_name);