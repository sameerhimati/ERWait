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

    // Listen for the event fired when the user selects a prediction and retrieve
    // more details for that place.
    searchBox.addListener("places_changed", () => {
        const places = searchBox.getPlaces();

        if (places.length == 0) {
            return;
        }

        // For each place, get the icon, name and location.
        const bounds = new google.maps.LatLngBounds();
        places.forEach((place) => {
            if (!place.geometry || !place.geometry.location) {
                console.log("Returned place contains no geometry");
                return;
            }

            if (place.geometry.viewport) {
                // Only geocodes have viewport.
                bounds.union(place.geometry.viewport);
            } else {
                bounds.extend(place.geometry.location);
            }
        });
        map.fitBounds(bounds);
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
        const response = await axios.get('/api/hospitals');
        const hospitals = response.data;
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

            marker.addListener('mouseover', () => {
                if (currentInfoWindow) {
                    currentInfoWindow.close();
                }
                infoWindow.open(map, marker);
                currentInfoWindow = infoWindow;
                if (userMarker) {
                    getTravelTime(userMarker.getPosition(), marker.getPosition(), hospital.name);
                }
            });

            marker.addListener('mouseout', () => {
                setTimeout(() => {
                    if (!infoWindow.getMap()) return;
                    infoWindow.close();
                    currentInfoWindow = null;
                }, 1000);
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

window.initMap = initMap;