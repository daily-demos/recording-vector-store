import {
  setupDailyControls,
  setupStoreQuery,
  setupUploadForm,
  updateStatus,
  updateUploads,
  enableStoreControls,
  setupIndexUploads,
  disableIndexUploads,
  disableStoreControls,
  enableStoreQuery,
  updateResponse,
  enableIndexUploads,
  updateUploadError,
  disableStoreQuery,
} from './dom.js';

const apiURL = 'http://127.0.0.1:5000';

window.addEventListener('DOMContentLoaded', () => {
  fetchCapabilities().then((capabilities) => {
    if (capabilities.daily === true) {
      setupDailyControls(indexDailyRecordings);
    }
  });
  setupUploadForm(uploadFiles);
  setupIndexUploads(indexUploads);
  setupStoreQuery(runQuery);
  pollVectorStoreStatus(1);
  pollUploads(1);
});

/**
 * Retrieve server capabilities
 * In this case, the specific value we care about is whether a Daily API key is configured
 * @returns {Promise<any>}
 */
function fetchCapabilities() {
  return fetch(`${apiURL}/status/capabilities`, { method: 'GET' })
    .then((res) => {
      if (res.ok === false) {
        throw Error(`Failed to fetch server capabilities: ${res.status}`);
      }
      return res.json();
    })
    .catch((e) => {
      console.error('Failed to fetch app capabilities:', e);
    });
}

/**
 * Upload files to the server for future indexing
 * @param files
 */
function uploadFiles(files) {
  // Clear upload error for fresh upload.
  updateUploadError('');
  const errors = [];

  for (let i = 0; i < files.length; i += 1) {
    const file = files[i];
    // Size sanity check; otherwise server will reject it anyway.
    if (file.size > 1000000 * 60) {
      errors.push(`File ${file.name} over 60MB size limit. Not uploading.`);
      continue;
    }
    const formData = new FormData();
    formData.append('file', file);

    // Upload the selected file to the server. This will begin processing the file
    // to remove filler words.
    fetch(`${apiURL}/upload`, { method: 'POST', body: formData })
      .then((res) => {
        if (res.ok === false) {
          throw Error(
            `upload request failed for file: ${res.status} {${file.name}`,
          );
        }
      })
      .catch((e) => {
        console.error(`Failed to upload file ${file.name}:`, e);
      });
  }
  updateUploadError(errors.join(' '));
}

/**
 * Index Daily recordings
 * @param roomName
 * @param maxRecordings
 */
function indexDailyRecordings(roomName, maxRecordings) {
  const body = {
    source: 'daily',
    room_name: roomName,
    max_recordings: maxRecordings,
  };
  doIndex(body);
}

/**
 * Index manually-uploaded files that are already on the server
 */
function indexUploads() {
  const body = {
    source: 'uploads',
  };
  doIndex(body);
}

/**
 * Instruct the server to commence index creation or update based on given configuration
 * @param body
 */
function doIndex(body) {
  fetch(`${apiURL}/db/index`, { method: 'POST', body: JSON.stringify(body) })
    .then((res) => {
      if (res.ok === false) {
        throw Error(`Unexpected status code: ${res.status}`);
      }
    })
    .catch((e) => {
      console.error('Failed to initialize or update database:', e);
    });
}

/**
 * Queries the existing index with the given input.
 * @param queryInput
 */
function runQuery(queryInput) {
  disableStoreQuery(true);
  fetch(`${apiURL}/db/query`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: queryInput,
    }),
  })
    .then((res) => {
      if (res.ok === false) {
        throw Error(`Unexpected status code: ${res.status}`);
      }
      return res.json();
    })
    .then((res) => {
      // Update the DOM with the retrieved response.
      const { answer } = res;
      updateResponse(answer);
      enableStoreQuery();
    })
    .catch((e) => {
      console.error('Failed to run query:', e);
    });
}

/**
 * Poll the status of the vector store
 * @param timeoutMs
 */
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
        const { state, message } = data;

        switch (state) {
          case 'uninitialized':
            updateStatus(state, message);
            enableStoreControls();
            pollVectorStoreStatus(3000);
            break;
          case 'updating':
            updateStatus(state, message, true);
            enableStoreQuery();
            pollVectorStoreStatus(3000);
            break;
          case 'ready':
            updateStatus(state, message);
            enableStoreQuery();
            enableStoreControls();
            // Poll less frequently if index is ready
            pollVectorStoreStatus(10000);
            break;
          case 'failed':
            updateStatus(state, message);
            enableStoreControls();
            pollVectorStoreStatus(3000);
            break;
          default:
            updateStatus(state, message, true);
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

/**
 * Checks which manual uploads are pending indexing on the server.
 * @param timeoutMs
 */
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
        const { files } = data;
        // If there are no uploads to index, disable index button
        if (files.length === 0) {
          disableIndexUploads();
        } else {
          enableIndexUploads();
        }

        // Update the DOM with the new uploaded file information
        updateUploads(files);
      })
      .catch((err) => {
        console.error('failed to check upload status: ', err);
      });
    pollUploads(5000);
  }, timeoutMs);
}
