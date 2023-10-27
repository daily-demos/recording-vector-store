import {
    addDailyRecording,
    addDownloadLink,
    addUploadedProject, enableDailyControls, enableStoreQuery,
    updateProjectStatus, updateStatus,
} from './dom.js';

window.addEventListener('DOMContentLoaded', () => {
    fetchCapabilities().then((capabilities) => {
        console.log("capabilities:", capabilities);
        if (capabilities["daily"] === true) {
            enableDailyControls(initFromDailyRecordings)
        }
    })

    pollVectorStoreStatus(1);
});

const apiURL = 'http://127.0.0.1:5000';

function initFromDailyRecordings(roomName, maxRecordings) {
    // Fetch all recordings from the server
    const body = {
        "room_name": roomName,
        "max_recordings": maxRecordings
    }
    console.log("initializing with body:", body)
    fetch(`${apiURL}/db/initialize`, { method: 'POST', body: JSON.stringify(body) })
        .then((res) => {
          if (res.ok === false) {
            throw Error(`Failed to initialize vector database: ${res.status}`);
          }
          console.log("initialized vector database")
        })
        .catch((e) => {
          console.error('Failed to initialize database:', e);
        });
}

function fetchCapabilities() {
    return fetch(`${apiURL}/capabilities`, { method: 'GET' })
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
          console.error('Failed to initialize database:', e);
        });
}

function runQuery(queryInput) {
    console.log("query:", queryInput)
        fetch(`${apiURL}/query`, {
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
                throw Error(`Failed to initialize vector database: ${res.status}`);
            }
            return res.json()
        }).then((res) => {
            console.log("answer:", res)
            const resEle = document.getElementById("response")
            resEle.innerText = res.answer
        }).catch((e) => {
            console.error('Failed to initialize database:', e);
        });
}

function pollVectorStoreStatus(timeoutMs) {
    setTimeout(() => {
        // Fetch status of the given project from the server
        fetch(`${apiURL}/db/status`)
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
                    case "ready":
                        enableStoreQuery(runQuery)
                        // Poll less frequently
                        pollVectorStoreStatus(10000);
                        break;
                    default:
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