// Initialize the map
const map = L.map('map').setView([37.7749, -122.4194], 10); // Set initial view to San Francisco

// Add the OpenStreetMap tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Function to fetch hospital data from your API
async function fetchHospitalData() {
    try {
        const response = await axios.get('/api/hospitals');
        return response.data;
    } catch (error) {
        console.error('Error fetching hospital data:', error);
        return [];
    }
}

// Function to add markers to the map
function addMarkersToMap(hospitals) {
    hospitals.forEach(hospital => {
        // You'll need to geocode the address to get lat/lon
        // For now, we'll use dummy coordinates
        const lat = 37.7749 + Math.random() * 0.1;
        const lon = -122.4194 + Math.random() * 0.1;
        
        const marker = L.marker([lat, lon]).addTo(map);
        marker.bindPopup(`<b>${hospital.name}</b><br>Address: ${hospital.address}<br>Wait time: ${hospital.waitTime}`);
    });
}

// Main function to initialize the map with data
async function initMap() {
    const hospitals = await fetchHospitalData();
    addMarkersToMap(hospitals);
}

// Call the main function
initMap();