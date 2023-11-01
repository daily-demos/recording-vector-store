const disabledClassName = "disabled";

export function setupDailyControls(onsubmit) {
  const form = document.getElementById("initFromRecordings");
  if (!form.onsubmit) {
    form.onsubmit = ((ev) => {
      console.log("SUBMITsTED")
      ev.preventDefault();
      const roomName = document.getElementById("roomName");
      const maxRecordings = document.getElementById("maxRecordings")
      onsubmit(roomName.value, maxRecordings.value);
      disableStoreControls();
    });
  }
}

export function enableStoreControls() {
  const pendingUploads = getUploadsEle();
  const listItems = pendingUploads.getElementsByTagName("li")
  if (listItems && listItems.length > 0) {
    enableBtn(getIndexUploadsButton());
  }

  const idxRecordingsForm = getIndexRecordingsForm()
  if (!idxRecordingsForm.onsubmit) return;
  enableBtn(getIndexRecordingsButton());
}

export function disableStoreControls() {
    disableIndexUploads()
    disableBtn(getIndexRecordingsButton())
}

function disableBtn(btn) {
  btn.disabled = true;
  btn.classList.add(disabledClassName)
}

function enableBtn(btn) {
  btn.disabled = false;
  btn.classList.remove(disabledClassName)
}

export function disableIndexUploads() {
    disableBtn(getIndexUploadsButton())
}

export function setupIndexUploads(onclick) {
  const btn = getIndexUploadsButton()
  // Only set onclick handler once
  if (!btn.onclick) {
    btn.onclick = ((ev) => {
      ev.preventDefault();
      disableStoreControls();
      onclick()
    });
  }
}

export function setupStoreQuery(onsubmit) {
     const form = document.getElementById("queryForm");
     form.onsubmit = (ev) => {
       ev.preventDefault();
       const query = document.getElementById("queryInput");
       onsubmit(query.value);
     }
}

export function enableStoreQuery() {
  enableBtn(getQueryButton())
}

export function updateStatus(state, msg) {
  const statusEle = document.getElementById("status");
  const spanEles = statusEle.getElementsByTagName("span")
  spanEles[0].innerText = state
  spanEles[1].innerText = msg
}

export function updateUploads(uploads) {
  const uploadsEle= getUploadsEle()
  if (uploads.length === 0) {
    uploadsEle.innerText = "No uploads pending indexing";
    return;
  }
  uploadsEle.innerText = "";
  // We could check for existing items and only replace the relevant ones here, but let's
  // just replace the whole list for simplicity of demonstration.
  const ul = document.createElement("ul")
  for (let i = 0; i < uploads.length; i += 1) {
    const upload = uploads[i];
    const li = document.createElement("li");
    li.innerText = upload;
    ul.append(li)
  }
  uploadsEle.append(ul);
}

function getUploadsEle() {
  return document.getElementById("uploads");
}

export function setupUploadForm(onsubmit) {
  const form = document.getElementById('uploadForm');
  form.onsubmit = (ev) => {
    ev.preventDefault();


    const files = document.getElementById('videoFiles').files;
    onsubmit(files)
  };
}

function getIndexUploadsButton() {
  return document.getElementById("indexUploads")
}

function getIndexRecordingsForm() {
    return document.getElementById("initFromRecordings");
}
function getIndexRecordingsButton() {
  return document.getElementById("indexRecordings")
}

function getQueryButton() {
  return document.getElementById("ask")
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
