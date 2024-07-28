// Define the API URL
const API_URL = '/api';

// Map functionality
let map, userMarker, markers = [];
let currentInfoWindow = null;

function initializeMap() {
    console.log("Initializing map");
    try {
        map = new google.maps.Map(document.getElementById('map'), {
            center: { lat: 39.8283, lng: -98.5795 },  // Center of US
            zoom: 4
        });
        
        getUserLocation();
        google.maps.event.addListenerOnce(map, 'idle', fetchHospitals);
    } catch (error) {
        console.error("Error initializing map:", error);
        showError("Failed to initialize the map. Please try refreshing the page.");
    }
}

function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            const userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };
            map.setCenter(userLocation);
            map.setZoom(10);
            if (userMarker) userMarker.setMap(null);
            userMarker = new google.maps.Marker({
                position: userLocation,
                map: map,
                title: "You are here"
            });
        }, function() {
            handleLocationError(true, map.getCenter());
        });
    } else {
        handleLocationError(false, map.getCenter());
    }
}

function handleLocationError(browserHasGeolocation, pos) {
    showError(browserHasGeolocation ?
        'Error: The Geolocation service failed.' :
        'Error: Your browser doesn\'t support geolocation.');
}

function fetchHospitals() {
    const bounds = map.getBounds();
    const center = bounds.getCenter();
    const ne = bounds.getNorthEast();

    // Calculate radius in miles
    const radius = google.maps.geometry.spherical.computeDistanceBetween(center, ne) / 1609.34;

    fetch(`${API_URL}/hospitals?lat=${center.lat()}&lon=${center.lng()}&radius=${radius}`)
        .then(response => response.json())
        .then(hospitals => {
            clearMarkers();
            addMarkersToMap(hospitals);
        })
        .catch(error => {
            console.error('Error fetching hospital data:', error);
            showError('Failed to fetch hospital data. Please try again later.');
        });
}

function clearMarkers() {
    markers.forEach(marker => marker.setMap(null));
    markers = [];
}

function addMarkersToMap(hospitals) {
    hospitals.forEach(hospital => {
        if (hospital.latitude && hospital.longitude) {
            const marker = new google.maps.Marker({
                position: { lat: hospital.latitude, lng: hospital.longitude },
                map: map,
                title: hospital.facility_name
            });

            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <b>${hospital.facility_name}</b><br>
                    Address: ${hospital.address}, ${hospital.city}, ${hospital.state} ${hospital.zip_code}<br>
                    ${hospital.wait_time ? `Wait time: ${hospital.wait_time} minutes<br>` : ''}
                    ${hospital.phone_number ? `Phone: ${hospital.phone_number}<br>` : ''}
                    ${hospital.has_live_wait_time ? '<p>Live wait times available</p>' : ''}
                `
            });

            marker.addListener('click', () => {
                if (currentInfoWindow) {
                    currentInfoWindow.close();
                }
                infoWindow.open(map, marker);
                currentInfoWindow = infoWindow;
            });

            markers.push(marker);
        }
    });
}

// Chat functionality
function initChat() {
    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
        chatForm.addEventListener('submit', handleChatSubmit);
    }
}

async function handleChatSubmit(e) {
    e.preventDefault();
    const userInput = document.getElementById('user-input').value;
    
    if (!userInput.trim()) return;

    displayChatMessage('user', userInput);
    document.getElementById('user-input').value = '';

    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: userInput }),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayChatMessage('bot', data.response);
    } catch (error) {
        console.error('Error:', error);
        displayChatMessage('bot', 'Sorry, there was an error processing your request.');
    }
}

function displayChatMessage(sender, message) {
    const chatMessages = document.getElementById('chat-messages');
    const messageElement = document.createElement('div');
    messageElement.classList.add(sender);
    messageElement.textContent = message;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Price comparison functionality
function initPriceComparison() {
    const priceComparisonForm = document.getElementById('price-comparison-form');
    if (priceComparisonForm) {
        priceComparisonForm.addEventListener('submit', handlePriceComparisonSubmit);
    }
}

async function handlePriceComparisonSubmit(e) {
    e.preventDefault();
    const zipCode = document.getElementById('zip-code').value;
    const treatment = document.getElementById('treatment').value;
    
    if (!zipCode.trim() || !treatment.trim()) {
        showError('Please enter both ZIP code and treatment.');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/price-comparison`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ zipCode, treatment }),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayPriceComparisonResults(data);
    } catch (error) {
        console.error('Error:', error);
        showError('Sorry, there was an error processing your request.');
    }
}

function displayPriceComparisonResults(results) {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = ''; // Clear previous results
    
    if (results.error) {
        showError(results.error);
        return;
    }
    
    results.forEach(result => {
        const resultElement = document.createElement('div');
        resultElement.textContent = `${result.facilityName}: $${result.price}`;
        resultsContainer.appendChild(resultElement);
    });
}

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const pageId = e.target.getAttribute('data-page');
            switchPage(pageId);
        });
    });
}

function switchPage(pageId) {
    document.querySelectorAll('.page').forEach(page => {
        page.style.display = 'none';
    });
    document.getElementById(`${pageId}-page`).style.display = 'block';
    if (pageId === 'map' && typeof initializeMap === 'function') {
        initializeMap();
    }
}

// Utility functions
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function hideError() {
    document.getElementById('error').style.display = 'none';
}

// Initialize all features
function initAll() {
    initNavigation();
    initChat();
    initPriceComparison();
    if (typeof google !== 'undefined') {
        initializeMap();
    } else {
        window.initializeMap = initializeMap;
    }
    switchPage('map'); // Set map as the default page
}

// Call initAll when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initAll);