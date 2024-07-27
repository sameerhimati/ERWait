// main.js

// Define the API URL
const API_URL = '/api';

// Map functionality
let map, userMarker, markers = [];
let currentInfoWindow = null;

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 35.1495, lng: -90.0490 },
        zoom: 10
    });

    // Add the search box
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Search for a location";

    const searchBox = new google.maps.places.SearchBox(input);
    map.controls[google.maps.ControlPosition.TOP_LEFT].push(input);

    // Bias the SearchBox results towards current map's viewport
    map.addListener("bounds_changed", () => {
        searchBox.setBounds(map.getBounds());
    });

    searchBox.addListener("places_changed", () => {
        const places = searchBox.getPlaces();

        if (places.length == 0) {
            return;
        }

        const bounds = new google.maps.LatLngBounds();
        places.forEach((place) => {
            if (!place.geometry || !place.geometry.location) {
                console.log("Returned place contains no geometry");
                return;
            }

            if (place.geometry.viewport) {
                bounds.union(place.geometry.viewport);
            } else {
                bounds.extend(place.geometry.location);
            }
        });
        map.fitBounds(bounds);
    });

    map.addListener('click', () => {
        if (currentInfoWindow) {
            currentInfoWindow.close();
            currentInfoWindow = null;
        }
    });

    getUserLocation();
    google.maps.event.addListener(map, 'idle', fetchHospitals);
}

function getUserLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            const userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };
            map.setCenter(userLocation);
            map.setZoom(13);
            if (userMarker) userMarker.setMap(null);
            userMarker = new google.maps.Marker({
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
                title: "You are here"
            });
        }, function(error) {
            console.error("Error getting user location:", error);
            showError("Unable to get your location. Please allow location access.");
        });
    } else {
        showError("Geolocation is not supported by your browser.");
    }
}

function fetchHospitals() {
    showLoading();
    hideError();

    const bounds = map.getBounds();
    const center = bounds.getCenter();
    const ne = bounds.getNorthEast();

    // Calculate radius in miles
    const radius = google.maps.geometry.spherical.computeDistanceBetween(center, ne) / 1609.34;

    fetch(`${API_URL}/hospitals?lat=${center.lat()}&lon=${center.lng()}&radius=${radius}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(hospitals => {
            clearMarkers();
            addMarkersToMap(hospitals);
            hideLoading();
        })
        .catch(error => {
            console.error('Error fetching hospital data:', error);
            showError('Failed to fetch hospital data. Please try again later.');
            hideLoading();
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
                title: hospital.facility_name,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 20,
                    fillColor: getWaitTimeColor(hospital.wait_time),
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 2
                }
            });

            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <b>${hospital.facility_name}</b><br>
                    Address: ${hospital.address}, ${hospital.city}, ${hospital.state} ${hospital.zip_code}<br>
                    ${hospital.wait_time ? `Wait time: ${hospital.wait_time} minutes<br>` : ''}
                    ${hospital.phone_number ? `Phone: ${hospital.phone_number}<br>` : ''}
                    ${hospital.has_live_wait_time ? '<p>Live wait times available</p>' : ''}
                    <div id="travel-time-${hospital.facility_id}">Calculating travel time...</div>
                    <button onclick="getDirections(${hospital.latitude}, ${hospital.longitude})">Get Directions</button>
                `
            });

            marker.addListener('click', (event) => {
                event.stop();
                if (currentInfoWindow) {
                    currentInfoWindow.close();
                }
                infoWindow.open(map, marker);
                currentInfoWindow = infoWindow;
                if (userMarker) {
                    getTravelTime(userMarker.getPosition(), marker.getPosition(), hospital.facility_id);
                }
            });

            markers.push(marker);
        } else {
            console.warn(`Missing coordinates for hospital: ${hospital.facility_name}`);
        }
    });
}

function getTravelTime(origin, destination, hospitalId) {
    const service = new google.maps.DistanceMatrixService();
    service.getDistanceMatrix(
        {
            origins: [origin],
            destinations: [destination],
            travelMode: 'DRIVING',
            drivingOptions: {
                departureTime: new Date(),
                trafficModel: 'bestguess'
            }
        },
        (response, status) => {
            if (status === 'OK') {
                const duration = response.rows[0].elements[0].duration_in_traffic.text;
                const distance = response.rows[0].elements[0].distance.text;
                document.getElementById(`travel-time-${hospitalId}`).innerHTML = 
                    `Travel time: ${duration}<br>Distance: ${distance}`;
            } else {
                console.error('Error fetching travel time:', status);
            }
        }
    );
}

function getWaitTimeColor(waitTime) {
    if (!waitTime) return '#808080';  // Gray for no data
    const time = parseInt(waitTime);
    if (time <= 15) return '#4CAF50';  // Green
    if (time <= 30) return '#FFC107';  // Yellow
    if (time <= 60) return '#FF9800';  // Orange
    return '#F44336';  // Red
}

function getDirections(lat, lon) {
    if (userMarker) {
        const directionsService = new google.maps.DirectionsService();
        const directionsRenderer = new google.maps.DirectionsRenderer();
        directionsRenderer.setMap(map);

        const request = {
            origin: userMarker.getPosition(),
            destination: { lat: lat, lng: lon },
            travelMode: 'DRIVING'
        };

        directionsService.route(request, function(result, status) {
            if (status === 'OK') {
                directionsRenderer.setDirections(result);
                if (currentInfoWindow) {
                    currentInfoWindow.close();
                    currentInfoWindow = null;
                }
            } else {
                showError("Unable to get directions. Please try again.");
            }
        });
    } else {
        showError("Please enable location services to get directions.");
    }
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function hideError() {
    document.getElementById('error').style.display = 'none';
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
        displayPriceComparisonResults({ error: 'Please enter both ZIP code and treatment.' });
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
        displayPriceComparisonResults({ error: 'Sorry, there was an error processing your request.' });
    }
}

function displayPriceComparisonResults(results) {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = ''; // Clear previous results
    
    if (results.error) {
        resultsContainer.textContent = results.error;
        return;
    }
    
    // Display the results (you'll need to format this based on your data structure)
    results.forEach(result => {
        const resultElement = document.createElement('div');
        resultElement.textContent = `${result.facilityName}: $${result.price}`;
        resultsContainer.appendChild(resultElement);
    });
}

// Initialize all features
function initAll() {
    if (document.getElementById('map')) {
        initMap();
    }
    initChat();
    initPriceComparison();
}

// Call initAll when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initAll);

// Make initMap globally available for the Google Maps API callback
window.initMap = initMap;