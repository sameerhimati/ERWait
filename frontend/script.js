// Initialize the map
const map = L.map('map').setView([35.1495, -90.0490], 10); // Set initial view to Memphis, TN

// Add the OpenStreetMap tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Create a marker cluster group
const markers = L.markerClusterGroup();

// Function to show loading indicator
function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

// Function to hide loading indicator
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// Function to show error message
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

// Function to hide error message
function hideError() {
    document.getElementById('error').style.display = 'none';
}

// Function to fetch hospital data from your API
async function fetchHospitalData() {
    showLoading();
    hideError();
    try {
        const response = await axios.get('/api/hospitals');
        console.log('API response:', response.data);
        return response.data;
    } catch (error) {
        console.error('Error fetching hospital data:', error);
        showError('Failed to fetch hospital data. Please try again later.');
        return [];
    } finally {
        hideLoading();
    }
}

// Function to add markers to the map
function addMarkersToMap(hospitals) {
    hospitals.forEach(hospital => {
        if (hospital.lat && hospital.lon) {
            const marker = L.marker([hospital.lat, hospital.lon]);
            marker.bindPopup(`<b>${hospital.name}</b><br>Address: ${hospital.address}<br>Wait time: ${hospital.waitTime}`);
            markers.addLayer(marker);
        } else {
            console.warn(`Missing coordinates for hospital: ${hospital.name}`);
        }
    });
    map.addLayer(markers);
    if (markers.getBounds().isValid()) {
        map.fitBounds(markers.getBounds());
    } else {
        console.warn('No valid bounds for markers');
    }
}

// Main function to initialize the map with data
async function initMap() {
    const hospitals = await fetchHospitalData();
    if (hospitals.length > 0) {
        addMarkersToMap(hospitals);
    } else {
        showError('No hospital data available');
    }
}

// Call the main function when the page loads
window.addEventListener('load', initMap);