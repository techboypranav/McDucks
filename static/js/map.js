// Initialize Map (Centered on India by default)
var map = L.map('map').setView([20.5937, 78.9629], 5);

// Add OpenStreetMap Tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Define custom icons (Optional: makes it look polished)
var greenIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
});

async function submitOrder() {
    const statusDiv = document.getElementById('statusMessage');
    statusDiv.innerHTML = '<div class="alert alert-info">📡 Acquiring GPS & calculating routes...</div>';

    // 1. Get Browser Location
    if (!navigator.geolocation) {
        statusDiv.innerHTML = '<div class="alert alert-danger">Geolocation is not supported by your browser.</div>';
        return;
    }

    navigator.geolocation.getCurrentPosition(async (position) => {
        const userLat = position.coords.latitude;
        const userLon = position.coords.longitude;

        // 2. Prepare Data
        const payload = {
            farmer_id: document.getElementById('farmer_id').value,
            crop_type: document.getElementById('crop_type').value,
            quantity: document.getElementById('quantity').value,
            lat: userLat,
            lon: userLon
        };

        try {
            // 3. Send to Backend
            const response = await fetch('/api/allocate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                // 4. Success UI Update
                statusDiv.innerHTML = `
                    <div class="alert alert-success">
                        <strong>Allocated to:</strong> ${result.warehouse_name}<br>
                        <strong>Distance:</strong> ${result.dist} km<br>
                        <strong>ETA:</strong> ${result.eta}
                    </div>
                `;

                // 5. Draw on Map
                // Clear previous layers if you want (optional)
                
                // Add Marker for Trader (Blue default)
                L.marker([userLat, userLon]).addTo(map)
                    .bindPopup("<b>Collection Point</b><br>Trader Location").openPopup();

                // Add Marker for Warehouse (Green)
                L.marker([result.wh_lat, result.wh_lon], {icon: greenIcon}).addTo(map)
                    .bindPopup(`<b>${result.warehouse_name}</b><br>Destination`);

                // Draw Line
                var latlngs = [
                    [userLat, userLon],
                    [result.wh_lat, result.wh_lon]
                ];
                var polyline = L.polyline(latlngs, {color: 'green', weight: 4, opacity: 0.7}).addTo(map);

                // Zoom map to fit the route
                map.fitBounds(polyline.getBounds());

                // Reload page after 3 seconds to update history table (Simple refresh strategy)
                setTimeout(() => location.reload(), 4000);

            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">Error: ${result.error}</div>`;
            }
        } catch (error) {
            statusDiv.innerHTML = `<div class="alert alert-danger">Network Error: ${error}</div>`;
        }

    }, (error) => {
        statusDiv.innerHTML = '<div class="alert alert-danger">Unable to retrieve location. Allow GPS access.</div>';
    });
}