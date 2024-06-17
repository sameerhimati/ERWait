drop table if exists hospital_pages cascade;
drop table if exists hospital_wait_times cascade;

CREATE TABLE hospital_pages (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255), -- optional, as a placeholder or general name for the network
    url TEXT,
    hospital_num INTEGER NOT NULL
);


CREATE TABLE hospital_wait_times (
    id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(255),
    hospital_address VARCHAR(255),
    wait_time VARCHAR(255),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (1, 'Edward Health Elmhurst','https://www.eehealth.org/services/emergency/wait-times/', 3);
INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (2, 'Piedmont','https://www.piedmont.org/emergency-room-wait-times/emergency-room-wait-times', 21);
INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (3, 'Baptist','https://www.baptistonline.org/services/emergency', 18);
INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (4, 'Northern Nevada Sparks','https://www.nnmc.com/services/emergency-medicine/er-at-northern-nevada-medical-center', 1);
INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (5, 'Northern Nevada Reno','https://www.nnmc.com/services/emergency-medicine/er-at-mccarran-nw', 1);
INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (6, 'Northern Nevada Spanish Springs','https://www.nnmc.com/services/emergency-medicine/er-at-spanish-springs', 1);
INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (7, 'Metro Health','https://www.metrohealth.org/emergency-room', 4);
-- INSERT INTO hospital_pages (id, hospital_name, url, hospital_num) values (8, 'HCA Houston','https://www.hcahoustonhealthcare.com/legal/er-wait-times', 19);
