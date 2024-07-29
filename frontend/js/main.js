// Define the API URL
const API_URL = '/api';

// Map functionality
let map, userMarker, markers = [];
let currentInfoWindow = null;

let currentPage = 1;
let isLoading = false;
let hasMoreData = true;
let socket;

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

    google.maps.event.addListener(map, 'idle', fetchHospitals);
    google.maps.event.addListener(map, 'zoom_changed', resetPagination);
    google.maps.event.addListener(map, 'bounds_changed', function() {
        if (map.getZoom() > 10 && !isLoading && hasMoreData) {
            fetchHospitals();
        }
    });
    
}

function resetPagination() {
    currentPage = 1;
    clearMarkers();
    hasMoreData = true;
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
            
            // Add a blue dot for user's location
            new google.maps.Marker({
                position: userLocation,
                map: map,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 10,
                    fillColor: "#4285F4",
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 2
                },
                title: "Your Location"
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

function initializeWebSocket() {
    socket = io(window.location.origin);

    socket.on('connect', () => {
        console.log('Connected to WebSocket');
        requestInitialData();
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from WebSocket');
    });

    socket.on('initial_data', (data) => {
        console.log('Received initial data:', data);
        addMarkersToMap(data.hospitals);
    });

    socket.on('wait_time_update', (data) => {
        console.log('Received wait time update:', data);
        updateMarkerWaitTime(data.hospital_id, data.new_wait_time);
    });
}

function requestInitialData() {
    const center = map.getCenter();
    const bounds = map.getBounds();
    const ne = bounds.getNorthEast();
    const radius = google.maps.geometry.spherical.computeDistanceBetween(center, ne) / 1609.34; // Convert to miles

    socket.emit('request_initial_data', {
        lat: center.lat(),
        lon: center.lng(),
        radius: radius
    });
}

function updateMarkerWaitTime(hospitalId, newWaitTime, isLive) {
    const marker = markers.find(m => m.hospitalId === hospitalId);
    if (marker) {
        marker.setIcon(getMarkerIcon(newWaitTime, isLive));
        marker.setLabel({
            text: newWaitTime !== 'N/A' ? `${newWaitTime}` : 'N/A',
            color: 'black',
            fontSize: '12px',
            fontWeight: 'bold'
        });
        
        if (currentInfoWindow && currentInfoWindow.anchor === marker) {
            const content = currentInfoWindow.getContent();
            const updatedContent = content.replace(
                /(?:Current|Average) wait time: .*<br>/,
                `${isLive ? 'Current' : 'Average'} wait time: ${newWaitTime !== 'N/A' ? `${newWaitTime} minutes` : 'Not available'}<br>`
            );
            currentInfoWindow.setContent(updatedContent);
        }
    }
}

function fetchHospitals() {
    if (isLoading || !hasMoreData) return;
    
    isLoading = true;
    showLoading();

    const bounds = map.getBounds();
    const center = bounds.getCenter();
    const ne = bounds.getNorthEast();

    // Calculate radius in miles
    const radius = google.maps.geometry.spherical.computeDistanceBetween(center, ne) / 1609.34;

    const url = `${API_URL}/hospitals?lat=${center.lat()}&lon=${center.lng()}&radius=${radius}&page=${currentPage}&per_page=50`;
    console.log('Fetching hospitals from:', url);

    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('Received hospital data:', data);
            console.log('Number of hospitals:', data.hospitals.length);
            console.log('Total count:', data.total_count);
            console.log('Current page:', data.page);
            console.log('Total pages:', data.total_pages);
            addMarkersToMap(data.hospitals);
            currentPage++;
            hasMoreData = currentPage <= data.total_pages;
            isLoading = false;
            hideLoading();
        })
        .catch(error => {
            console.error('Error fetching hospital data:', error);
            showError('Failed to fetch hospital data. Please try again later.');
            isLoading = false;
            hideLoading();
        });
}

function getMarkerIcon(waitTime, isLive) {
    const size = new google.maps.Size(30, 30);
    const anchor = new google.maps.Point(15, 30);
    let url;

    if (waitTime === null || waitTime === undefined || waitTime === 'N/A') {
        url = 'https://maps.google.com/mapfiles/ms/icons/gray-dot.png';
    } else {
        waitTime = parseInt(waitTime);
        if (isLive) {
            if (waitTime <= 15) {
                url = 'https://maps.google.com/mapfiles/ms/icons/green-dot.png';
            } else if (waitTime <= 30) {
                url = 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png';
            } else if (waitTime <= 60) {
                url = 'https://maps.google.com/mapfiles/ms/icons/orange-dot.png';
            } else {
                url = 'https://maps.google.com/mapfiles/ms/icons/red-dot.png';
            }
        } else {
            url = 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png'; // Historical data
        }
    }

    return {
        url: url,
        size: size,
        anchor: anchor,
        scaledSize: size
    };
}


function clearMarkers() {
    markers.forEach(marker => marker.setMap(null));
    markers = [];
}

function addMarkersToMap(hospitals) {
    console.log('Adding markers for hospitals:', hospitals);
    hospitals.forEach(hospital => {
        const lat = parseFloat(hospital.latitude);
        const lng = parseFloat(hospital.longitude);
        
        if (!isNaN(lat) && !isNaN(lng)) {
            const waitTime = hospital.wait_time !== undefined ? hospital.wait_time : 'N/A';
            const isLive = hospital.has_live_wait_time;
            const marker = new google.maps.Marker({
                position: { lat, lng },
                map: map,
                title: hospital.facility_name,
                hospitalId: hospital.id,
                icon: getMarkerIcon(waitTime, isLive),
                label: {
                    text: waitTime !== 'N/A' ? `${waitTime}` : 'N/A',
                    color: 'black',
                    fontSize: '12px',
                    fontWeight: 'bold'
                }
            });

            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <b>${hospital.facility_name}</b><br>
                    Address: ${hospital.address}, ${hospital.city}, ${hospital.state} ${hospital.zip_code}<br>
                    ${isLive ? `Current wait time: ${waitTime} minutes` : 
                               waitTime !== 'N/A' ? `Average wait time: ${waitTime} minutes` : 'Wait time: Not available'}<br>
                    ${hospital.phone_number ? `Phone: ${hospital.phone_number}<br>` : ''}
                    ${isLive ? '<p>Live wait times available</p>' : ''}
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
        } else {
            console.warn('Invalid coordinates for hospital:', hospital);
        }
    });
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
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
    if (typeof google !== 'undefined') {
        initializeMap();
    } else {
        window.initializeMap = initializeMap;
    }
    switchPage('map');
    initNavigation();
    initChat();
    initPriceComparison();
    initializeWebSocket();
}

// Call initAll when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initAll);