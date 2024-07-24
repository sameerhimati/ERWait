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
    fetchHospitalData();
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

async function fetchHospitalData() {
    showLoading();
    hideError();
    try {
        const response = await fetch(`${API_URL}/hospitals`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const hospitals = await response.json();
        addMarkersToMap(hospitals);
    } catch (error) {
        console.error('Error fetching hospital data:', error);
        showError('Failed to fetch hospital data. Please try again later.');
    } finally {
        hideLoading();
    }
}

function addMarkersToMap(hospitals) {
    hospitals.forEach(hospital => {
        if (hospital.lat && hospital.lon) {
            const marker = new google.maps.Marker({
                position: { lat: hospital.lat, lng: hospital.lon },
                map: map,
                title: hospital.name,
                label: {
                    text: hospital.waitTime + ' min',
                    color: 'white',
                    fontSize: '12px'
                },
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 20,
                    fillColor: getWaitTimeColor(hospital.waitTime),
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 2
                }
            });

            const infoWindow = new google.maps.InfoWindow({
                content: `
                    <b>${hospital.name}</b><br>
                    Address: ${hospital.address}<br>
                    Wait time: ${hospital.waitTime} minutes<br>
                    Network: ${hospital.networkName}<br>
                    <a href="${hospital.website}" target="_blank">Visit Website</a><br>
                    <div id="travel-time-${hospital.name.replace(/\s+/g, '-')}">Calculating travel time...</div>
                    <button onclick="getDirections(${hospital.lat}, ${hospital.lon})">Get Directions</button>
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
                    getTravelTime(userMarker.getPosition(), marker.getPosition(), hospital.name);
                }
            });

            markers.push(marker);
        } else {
            console.warn(`Missing coordinates for hospital: ${hospital.name}`);
        }
    });

    if (markers.length > 0) {
        const bounds = new google.maps.LatLngBounds();
        markers.forEach(marker => bounds.extend(marker.getPosition()));
        map.fitBounds(bounds);
    } else {
        console.warn('No valid markers to set bounds');
    }
}

function getTravelTime(origin, destination, hospitalName) {
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
                document.getElementById(`travel-time-${hospitalName.replace(/\s+/g, '-')}`).innerHTML = 
                    `Travel time: ${duration}<br>Distance: ${distance}`;
            } else {
                console.error('Error fetching travel time:', status);
            }
        }
    );
}

function getWaitTimeColor(waitTime) {
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