# Face Recognition Access Control Node-RED Project

## 1. Project Overview

This project is a complete face recognition access control system implemented in Node-RED. It is designed as a highly integrated and configurable central hub, responsible for processing data streams from edge vision devices (like the Grove Vision AI V2), invoking remote AI services for face feature extraction, comparing them against a vector database (Qdrant), and making final access decisions.

The flow supports two core functions: real-time face recognition and manual face enrollment. It uses the MQTT protocol for communication and status monitoring with other system components.

---

## 2. Core Features

- **Real-time Face Recognition**: Processes video frames from a camera, recognizes faces, compares them with a database, and makes "allow" or "deny" access decisions.
- **Dynamic Face Enrollment**: Manually triggered process to collect multiple frames of a specified user's face, calculate an average feature vector, and store it in a designated database (Collection).
- **Edge Device Integration**: Optimized for the **Grove Vision AI V2**, correctly parsing its unique center-point coordinate BBox format.
- **Remote AI Service Invocation**: Calls the externally deployed **FaceEmbed API** via HTTP request to convert face images into 512-dimension feature vectors.
- **Vector Database Integration**: Deeply integrated with **Qdrant** for storing and rapidly retrieving face vectors.
- **System Status Monitoring**: Uses an MQTT **heartbeat mechanism** to periodically publish system health and key configuration information for remote monitoring and debugging.
- **Flexible Configuration**: All key parameters (IP addresses, device mappings, similarity thresholds, database names) are configured within Node-RED nodes, without needing to modify environment variables.

---

## 3. Flow Architecture

The system primarily consists of two parallel logical flows: the **Recognition Flow** and the **Enrollment Flow**.

### Recognition Flow
```
Grove Vision AI V2 → [Process Vision Frame] → [FaceEmbed API] → [Prepare Vector Search] → [Qdrant Search] → [Make Access Decision] → Publish Result (MQTT)
```

### Enrollment Flow
```
Manual Trigger (Inject) → [Process Vision Frame] → [FaceEmbed API] → [Collect/Average/Store Vector] → [Qdrant Upsert] → Publish Status (MQTT)
```

---

## 4. Key Node Explanations

### `[Grove Vision AI V2]` (Subflow)
- **Purpose**: Acts as the source for video and face detection data.
- **Outputs**:
    - **Output 1 (Image)**: Raw image data.
    - **Output 2 (Detection Results)**: An array of face bounding boxes.
- **Note**: This project keeps the subflow's internals unchanged; all adaptations are handled externally.

### `[Grove Data Combiner]` (Function)
- **Purpose**: The project's core adapter, which merges the two outputs from the Grove device into a standard data format.
- **Core Logic**:
    1.  Receives and temporarily stores image data.
    2.  Receives detection results and matches them with the corresponding image.
    3.  **Correctly handles the Grove's `[center_x, center_y, width, height]` BBox format**, converting it to the standard top-left corner format.
    4.  Outputs a unified message containing the image and the standardized BBox.

### `[Process Vision Frame]` (Function)
- **Purpose**: The data flow's **main router**.
- **Core Logic**: Checks if the system is currently in "enrollment mode".
    - **No (Normal Recognition)**: Sends the message from **Output 1** to the recognition flow.
    - **Yes (Face Enrollment)**: Sends the message from **Output 2** to the enrollment flow.

### `[Collect/Average/Store Vector]` (Function)
- **Purpose**: The **core processor** for face enrollment.
- **Core Logic**:
    1.  **Collects** vectors from 10 face images.
    2.  **Calculates** the **average** of these 10 vectors to generate a more stable face template.
    3.  **Prepares** the Qdrant upsert request, including the average vector and the user's name.
    4.  **Updates** the enrollment progress in real-time via MQTT.

---

## 5. Installation and Configuration

### Dependencies
Before starting this Node-RED flow, ensure the following external services are running:
- **MQTT Broker**: For message communication.
- **Qdrant Database**: For storing and searching vectors.
- **FaceEmbed API**: The face feature extraction service deployed on an AI accelerator device (e.g., Hailo).

### Importing the Flow
1.  Copy the entire content of the `face_access_control.json` file.
2.  In the Node-RED interface, click the top-right menu > `Import`.
3.  Paste the JSON content into the input box and click `Import`.

### Parameter Configuration (Greatly Simplified)
All key parameters are now set in the `[Global Config (Load on Start)]` node. This node runs automatically once when Node-RED starts, loading the configuration into the Flow context.

**You only need to modify this single node to adjust the entire system's behavior.**

1.  **Find the `[Global Config (Load on Start)]` node** in the top-left corner of the flow.
2.  **Double-click to open it** and edit its code to configure the following parameters:
    - **Qdrant Vector Database Address**:
      - `flow.set('qdrant_host', 'localhost');`
      - `flow.set('qdrant_port', '6333');`
      - `flow.set('qdrant_api_key', 'face_access_2025');`
    - **Hailo Face Embedding API Address**:
      - `flow.set('hailo_host', '192.168.10.179');`
      - `flow.set('hailo_port', '8000');`
    - **Camera Image Dimensions**:
      - `flow.set('image_width', 480);`
      - `flow.set('image_height', 480);`

---

## 6. Usage Guide

### Start/Stop the Camera
- Click the `Start` Inject node to begin the data stream from the Grove Vision AI V2.
- Click the `Stop` Inject node to halt the data stream.

### Face Enrollment
1.  Find the `[Face Enroll]` Inject node.
2.  **Edit the node** and modify the JSON data in the Payload:
    - `name`: The name of the user to enroll.
    - `collection`: The name of the Qdrant collection to store the face in (e.g., "office_entrance" or "warehouse_door").
    ```json
    {
      "name": "Jane Smith",
      "action": "start",
      "collection": "warehouse_door"
    }
    ```
3.  After deploying, click the button to the left of this node to **start the enrollment process with one click**.
4.  You can monitor the real-time progress by subscribing to the `access/enroll_status/+` topic with an MQTT client.

### Monitoring Recognition Results
- Subscribe to the MQTT topic `access/result/+` to see real-time access control results.

---

## 7. MQTT API Reference

- `access/result/{device_id}` (Output)
  - **Payload**: A JSON object with the access decision result, including the recognized name, distance score, timestamp, etc.
- `access/enroll_status/{device_id}` (Output)
  - **Payload**: A JSON object with the face enrollment status, including progress, success, or failure information.
- `system/heartbeat` (Output)
  - **Payload**: A JSON object with system heartbeat information, published every 60 seconds, containing system status and key configurations.

---

## 8. Troubleshooting

- **Not receiving recognition results**:
  1.  Check if the `Start` node has been triggered.
  2.  Look at the Node-RED debug sidebar to see if the `[Grove Data Combiner]` is outputting data.
  3.  Confirm that the FaceEmbed API and Qdrant services are accessible.
- **Face enrollment fails**:
  1.  Check if the `collection` name in the `Face Enroll` Inject node is correct.
  2.  Ensure there is a face in front of the camera with good lighting.
- **"No image data found" warning**:
  - This is usually a timing issue between the image and detection result messages. The system will automatically ignore mismatched data, so occasional warnings are normal. If they persist, check the Grove device's network connection. 