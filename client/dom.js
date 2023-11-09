const disabledClassName = 'disabled';

/**
 * Configures the handler for the Daily recording indexing form.
 * @param onsubmit
 */
export function setupDailyControls(onsubmit) {
  const form = document.getElementById('initFromRecordings');
  if (!form.onsubmit) {
    form.onsubmit = (ev) => {
      ev.preventDefault();
      const roomName = document.getElementById('roomName');
      const maxRecordings = document.getElementById('maxRecordings');
      onsubmit(roomName.value, maxRecordings.value);
      disableStoreControls();
    };
  }
}

/**
 * Configures the click handler for the upload-indexing button
 * @param onclick
 */
export function setupIndexUploads(onclick) {
  const btn = getIndexUploadsButton();
  // Only set onclick handler once
  if (!btn.onclick) {
    btn.onclick = (ev) => {
      ev.preventDefault();
      disableStoreControls();
      onclick();
    };
  }
}

/**
 * Sets up the submission handler for the querying form
 * @param onsubmit
 */
export function setupStoreQuery(onsubmit) {
  const form = document.getElementById('queryForm');
  form.onsubmit = (ev) => {
    ev.preventDefault();
    const query = document.getElementById('queryInput');
    onsubmit(query.value);
  };
}

/**
 * Set up video file upload form.
 * @param onsubmit
 */
export function setupUploadForm(onsubmit) {
  const form = document.getElementById('uploadForm');
  form.onsubmit = (ev) => {
    ev.preventDefault();

    const { files } = document.getElementById('videoFiles');
    onsubmit(files);
  };
}

export function updateUploadError(errMsg) {
  const ele = document.getElementById('uploadError');
  ele.innerText = errMsg;
}

/**
 * Enables store-related controls (i.e., triggering indexing)
 */
export function enableStoreControls() {
  const pendingUploads = getUploadsPendingIndexingEle();
  // Only enable the upload-indexing button if there are uploaded files to index.
  const listItems = pendingUploads.getElementsByTagName('li');
  if (listItems && listItems.length > 0) {
    enableIndexUploads();
  }

  // Only enable the Daily-recording-indexing button if it's been configured.
  // If no submission handler exists, the server doesn't have Daily capability enabled.
  const idxRecordingsForm = getIndexRecordingsForm();
  if (!idxRecordingsForm.onsubmit) return;
  enableBtn(getIndexRecordingsButton());
}

export function enableUploadBtn() {
  const uploadBtn = getUploadFilesBtn();
  // Reset inner text to remove spinner
  // (could also retrieve spinner by class name,
  // but this seems simpler for our demo purposes)
  uploadBtn.innerText = 'Upload';
  enableBtn(uploadBtn);
}

export function disableUploadBtn() {
  const uploadBtn = getUploadFilesBtn();
  disableBtn(uploadBtn);
  uploadBtn.append(createSpinner());
}

/**
 * Disables store-related controls (i.e., triggering indexing)
 */
export function disableStoreControls() {
  disableIndexUploads();
  disableBtn(getIndexRecordingsButton());
}

/**
 * Disable upload-indexing button
 * (in its own function as it also needs to be called externally)
 */
export function disableIndexUploads() {
  disableBtn(getIndexUploadsButton());
}

/**
 * Enable upload-indexing button.
 * (in its own function as it also needs to be called externally)
 */
export function enableIndexUploads() {
  enableBtn(getIndexUploadsButton());
}

/**
 * Enables query button
 */
export function enableStoreQuery() {
  const btn = getQueryButton();
  const spinners = btn.getElementsByClassName('spinner');
  if (spinners && spinners[0]) {
    spinners[0].remove();
  }
  enableBtn(getQueryButton());
}

export function disableStoreQuery(withSpinner) {
  const btn = getQueryButton();
  if (withSpinner) {
    btn.append(createSpinner());
  }
  disableBtn(getQueryButton());
}

/**
 * Update the response DOM element
 * @param response
 */
export function updateResponse(response) {
  const resEle = document.getElementById('response');
  resEle.innerText = response;
}

/**
 * Disable given button
 * @param btn
 */
function disableBtn(btn) {
  btn.disabled = true;
  btn.classList.add(disabledClassName);
}

/**
 * Enable given button
 * @param btn
 */
function enableBtn(btn) {
  btn.disabled = false;
  btn.classList.remove(disabledClassName);
}

/**
 * Updates store status DOM element
 * @param state
 * @param msg
 * @param isSpinning
 */
export function updateStatus(state, msg, isSpinning) {
  const statusEle = document.getElementById('status');
  const spanEles = statusEle.getElementsByTagName('span');

  const statusName = spanEles[0];
  if (!statusName.innerText.includes(state)) {
    statusName.innerText = '';
    if (isSpinning) {
      statusName.append(createSpinner());
    }
    statusName.append(state);
  }
  spanEles[1].innerText = msg;
}

/**
 * Updates the list of manually-uploaded files pending indexing
 * @param uploads
 */
export function updateUploadsPendingIndexing(uploads) {
  const uploadsEle = getUploadsPendingIndexingEle();
  if (uploads.length === 0) {
    uploadsEle.innerText = 'No uploads pending indexing';
    return;
  }
  updateListOfUploads(uploads, uploadsEle);
}

/**
 * Updates the list of manually-uploaded files currently being uploaded
 * @param uploads
 */
export function updateUploadsInProgress(uploads) {
  const uploadsEle = getUploadsInProgressEle();
  if (uploads.length === 0) {
    uploadsEle.innerText = 'No uploads in progress';
    return;
  }
  updateListOfUploads(uploads, uploadsEle, true);
}

/**
 * Updates the given element with a list of the given uploads
 * @param uploads
 * @param listContainer
 * @param withSpinner
 */
function updateListOfUploads(uploads, listContainer, withSpinner) {
  listContainer.innerText = '';
  // We could check for existing items and only replace the relevant ones here, but let's
  // just replace the whole list for simplicity of demonstration.
  const ul = document.createElement('ul');
  for (let i = 0; i < uploads.length; i += 1) {
    const upload = uploads[i];
    const li = document.createElement('li');
    li.innerText = upload;
    if (withSpinner) {
      li.append(createSpinner());
    }
    ul.append(li);
  }
  listContainer.append(ul);
}

function getUploadsPendingIndexingEle() {
  return document.getElementById('pendingIndexingUploads');
}

function getUploadsInProgressEle() {
  return document.getElementById('inProgressUploads');
}

function getIndexUploadsButton() {
  return document.getElementById('indexUploads');
}

function getUploadFilesBtn() {
  return document.getElementById('upload');
}

function getIndexRecordingsForm() {
  return document.getElementById('initFromRecordings');
}
function getIndexRecordingsButton() {
  return document.getElementById('indexRecordings');
}

function getQueryButton() {
  return document.getElementById('ask');
}

/**
 * Create a spinner element to show processing in progress.
 * @returns {HTMLDivElement}
 */
function createSpinner() {
  const ele = document.createElement('div');
  ele.className = 'spinner';
  return ele;
}
