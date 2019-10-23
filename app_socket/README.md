# Flask WebSocket Application for Disk Stats Monitoring

## Description

This is a Flask application using WebSocket for monitoring disk statistics by fetching data from Prometheus. It includes a server-side background process that periodically sends events to clients. Clients can request statistics for specific disks, and the server responds with data retrieved from Prometheus.

## Project Structure

Since this is a single-file project, all functionality is included in the main file:

- `app.py` - The main file that initializes Flask, handles WebSocket events, fetches metrics from Prometheus, and manages client connections.

## Requirements

- Python 3.8+
- Flask
- Flask-SocketIO
- Requests
- Prometheus Client

### Installing Dependencies

1. Ensure you have Python 3.8+ installed.
2. Install the required dependencies by running:

```bash
pip install -r requirements.txt
```

Your requirements.txt should include the following:

```txt
Flask
Flask-SocketIO
requests
prometheus_client
```

### Running the Application

To start the application, execute the following command:

```bash
python3 app.py
```

The application will be available at http://0.0.0.0:8080/.

### Usage

#### WebSocket

The application uses WebSocket to communicate with clients. The connection occurs through the /ws/disk_stats namespace. Examples of WebSocket events include:
    1. on_connect - When a client successfully connects.
    2. on_disconnect - When a client disconnects.
    3. on_my_ping - Receives a "ping" request and sends back a "pong" response.
    4. on_send_stats - Clients send a list of disks to this event to request disk statistics.

#### Example WebSocket Usage

You can use a WebSocket client library such as socket.io-client to connect:

```javascript
const socket = io.connect('http://localhost:8080/ws/disk_stats');

// On connection
socket.on('response', (data) => {
    console.log('Message from server:', data);
});

// Request disk statistics
socket.emit('send_stats', { disks: 'disk1,disk2' });

// Ping-pong
socket.emit('my_ping');
socket.on('pong', () => {
    console.log('Pong received');
});

```

### Prometheus Integration

The application expects a Prometheus server to be available at the
address defined by the CEPH_PROMETHEUS_HOST constant (e.g., http://10.254.20.50:9285/api/v1/metrics).
Metrics are filtered by the ceph_librbd_ prefix and processed before being sent to clients.

### Logging

Logging is configured to provide detailed information at the DEBUG level. You can adjust logging settings directly in the app.py file.