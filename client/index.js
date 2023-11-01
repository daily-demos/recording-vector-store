import {
    setupDailyControls,
    setupStoreQuery,
    setupUploadForm,
    updateStatus,
    updateUploads,
    enableStoreControls, setupIndexUploads, disableIndexUploads, disableStoreControls, enableStoreQuery,
} from './dom.js';

const apiURL = 'http://127.0.0.1:5000';

window.addEventListener('DOMContentLoaded', () => {
    fetchCapabilities().then((capabilities) => {
        console.log("capabilities:", capabilities);
        if (capabilities["daily"] === true) {
            setupDailyControls(indexFromDailyRecordings)
        }
    })
    setupUploadForm(uploadFiles);
    setupIndexUploads(indexFromUploads);
    setupStoreQuery(runQuery)
    pollVectorStoreStatus(1);
    pollUploads(1)
});

function uploadFiles(files) {
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const formData = new FormData();
      formData.append('file', file);

      // Upload the selected file to the server. This will begin processing the file
      // to remove filler words.
      fetch(`${apiURL}/upload`, { method: 'POST', body: formData })
        .then((res) => {
          if (res.ok === false) {
            throw Error(`upload request failed for file: ${res.status} {${file.name}`);
          }
        })
        .catch((e) => {
          console.error(`Failed to upload file ${file.name}:`, e);
        });
      }
}

function indexFromDailyRecordings(roomName, maxRecordings) {
    // Fetch all recordings from the server
    const body = {
        "source": "daily",
        "room_name": roomName,
        "max_recordings": maxRecordings
    }
    doIndex(body)
}

function indexFromUploads() {
    // Fetch all recordings from the server
    const body = {
        "source": "uploads",
    }
    doIndex(body)
}

function doIndex(body) {
        fetch(`${apiURL}/db/index`, { method: 'POST', body: JSON.stringify(body) })
        .then((res) => {
          if (res.ok === false) {
            throw Error(`Unexpected status code: ${res.status}`);
          }
          console.log("initialized or updated vector database")
        })
        .catch((e) => {
          console.error('Failed to initialize or update database:', e);
        });
}

function fetchCapabilities() {
    return fetch(`${apiURL}/status/capabilities`, { method: 'GET' })
        .then((res) => {
          if (res.ok === false) {
            throw Error(`Failed to fetch server capabilities: ${res.status}`);
          }
          return res.json();
        })
        .then((data) => {
            return data;
        })
        .catch((e) => {
          console.error('Failed to fetch app capabilities:', e);
        });
}

function runQuery(queryInput) {
    console.log("query:", queryInput)
        fetch(`${apiURL}/db/query`, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: queryInput
            })
        }).then((res) => {
            if (res.ok === false) {
                throw Error(`Unexpected status code: ${res.status}`);
            }
            return res.json()
        }).then((res) => {
            console.log("answer:", res)
            const resEle = document.getElementById("response")
            resEle.innerText = res.answer
        }).catch((e) => {
            console.error('Failed to run query:', e);
        });
}

function pollVectorStoreStatus(timeoutMs) {
    setTimeout(() => {
        // Fetch status of the given project from the server
        fetch(`${apiURL}/status/db`)
            .then((res) => {
                if (!res.ok) {
                    throw Error(`status request failed: ${res.status}`);
                }
                return res.json();
            })
            .then((data) => {
                console.log("status data:", data)
                const {state, message} = data;
                updateStatus(state, message)

                switch (state) {
                    case "uninitialized":
                        enableStoreControls();
                        pollVectorStoreStatus(3000);
                        break;
                    case "ready":
                        enableStoreQuery();
                        enableStoreControls();
                        // Poll less frequently
                        pollVectorStoreStatus(10000);
                        break;
                    case "failed":
                        enableStoreControls();
                        pollVectorStoreStatus(3000);
                        break;
                    default:
                        disableStoreControls();
                        pollVectorStoreStatus(3000);
                        break;
                }
            })
            .catch((err) => {
                console.error('failed to check project status: ', err);
                pollVectorStoreStatus(3000);

            });
    }, timeoutMs);
}

function pollUploads(timeoutMs) {
    setTimeout(() => {
        // Fetch status of the given project from the server
        fetch(`${apiURL}/status/uploads`)
            .then((res) => {
                if (!res.ok) {
                    throw Error(`upload retrieval request failed: ${res.status}`);
                }
                return res.json();
            })
            .then((data) => {
                console.log("uploads status data:", data)
                const files = data["files"]
                if (files.length === 0) {
                    disableIndexUploads();
                }
                updateUploads(files);
                pollUploads(5000);
            })
            .catch((err) => {
                console.error('failed to check upload status: ', err);
                pollUploads(3000);
            });
    }, timeoutMs);
}