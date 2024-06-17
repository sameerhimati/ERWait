CREATE TABLE hospital_pages (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255),
    hospital_address VARCHAR(255),
    url TEXT
);

CREATE TABLE hospital_wait_times (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255),
    hospital_address VARCHAR(255),
    wait_time VARCHAR(255),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


