'use strict';

/* uploadFile(file) — POST FormData to /dochat/admin/ingest/upload
   Sets drop zone to 'uploading' state, POSTs file, handles success/error. */
function uploadFile(file) {
  var dropZone = document.getElementById('drop-zone');
  var spinner = document.getElementById('spinner');
  var dropZoneLabel = document.getElementById('drop-zone-label');
  var browseBtn = document.getElementById('browse-btn');
  var fileInput = document.getElementById('file-input');

  dropZone.classList.add('uploading');
  spinner.hidden = false;
  dropZoneLabel.hidden = true;
  browseBtn.disabled = true;
  fileInput.disabled = true;

  var formData = new FormData();
  formData.append('file', file);

  fetch('/dochat/admin/ingest/upload', {
    method: 'POST',
    body: formData,
  })
    .then(function(res) {
      return res.json().then(function(data) { return { ok: res.ok, data: data }; });
    })
    .then(function(result) {
      resetDropZone();
      if (result.ok) {
        appendDocRow(result.data);
      } else {
        showError('Upload failed: ' + (result.data.error || 'Unknown error') + '. Please try again.');
      }
    })
    .catch(function() {
      resetDropZone();
      showError('Could not reach the server. Check your connection and try again.');
    });
}

/* submitUrl(url) — POST JSON to /dochat/admin/ingest/url */
function submitUrl(url) {
  var urlInput = document.getElementById('url-input');
  var urlSubmitBtn = document.getElementById('url-submit-btn');

  urlInput.disabled = true;
  urlSubmitBtn.disabled = true;
  urlSubmitBtn.textContent = 'Crawling...';

  fetch('/dochat/admin/ingest/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: url }),
  })
    .then(function(res) {
      return res.json().then(function(data) { return { ok: res.ok, data: data }; });
    })
    .then(function(result) {
      resetUrlForm();
      if (result.ok) {
        appendDocRow(result.data);
      } else {
        showError('Upload failed: ' + (result.data.error || 'Unknown error') + '. Please try again.');
      }
    })
    .catch(function() {
      resetUrlForm();
      showError('Could not reach the server. Check your connection and try again.');
    });
}

/* appendDocRow(doc) — prepend <tr> to #doc-table-body
   doc shape: {doc_id, filename, type, upload_date, status, chunk_count} */
function appendDocRow(doc) {
  var tbody = document.getElementById('doc-table-body');
  if (!tbody) return;

  // Remove empty-state row if present
  var emptyRow = tbody.querySelector('tr td[colspan]');
  if (emptyRow) emptyRow.parentElement.remove();

  var tr = document.createElement('tr');
  tr.id = 'doc-row-' + doc.doc_id;
  tr.setAttribute('data-doc-id', doc.doc_id);
  tr.innerHTML =
    '<td>' + escapeHtml(doc.filename) + '</td>' +
    '<td>' + escapeHtml(doc.type || '') + '</td>' +
    '<td><time datetime="' + escapeHtml(doc.upload_date || '') + '">' + escapeHtml(doc.upload_date || '') + '</time></td>' +
    '<td><span class="status-badge status-' + escapeHtml(doc.status || 'ready') + '">' + escapeHtml(doc.status || 'ready') + '</span></td>' +
    '<td style="text-align:right">' + (doc.chunk_count || 0) + '</td>' +
    '<td style="text-align:center"><button class="delete-btn" data-doc-id="' + escapeHtml(doc.doc_id) + '" data-filename="' + escapeHtml(doc.filename) + '" aria-label="Delete ' + escapeHtml(doc.filename) + '" title="Delete document">&#x2715;</button></td>';
  tbody.prepend(tr);
}

/* showError(message) — show inline error box below upload area */
function showError(message) {
  var errorBox = document.getElementById('upload-error');
  var errorText = document.getElementById('upload-error-text');
  if (!errorBox || !errorText) return;
  errorText.textContent = message;
  errorBox.hidden = false;
}

/* resetDropZone() — return drop zone to ready state */
function resetDropZone() {
  var dropZone = document.getElementById('drop-zone');
  var spinner = document.getElementById('spinner');
  var dropZoneLabel = document.getElementById('drop-zone-label');
  var browseBtn = document.getElementById('browse-btn');
  var fileInput = document.getElementById('file-input');

  dropZone.classList.remove('uploading');
  spinner.hidden = true;
  dropZoneLabel.hidden = false;
  browseBtn.disabled = false;
  fileInput.disabled = false;
  fileInput.value = '';
}

/* resetUrlForm() — return URL form to ready state */
function resetUrlForm() {
  var urlInput = document.getElementById('url-input');
  var urlSubmitBtn = document.getElementById('url-submit-btn');
  if (!urlInput || !urlSubmitBtn) return;
  urlInput.disabled = false;
  urlInput.value = '';
  urlSubmitBtn.disabled = false;
  urlSubmitBtn.textContent = 'Crawl & Index';
}

/* deleteDoc(docId, filename) — confirm + DELETE + remove row */
function deleteDoc(docId, filename) {
  if (!confirm('Delete ' + filename + '? This removes all indexed chunks.')) return;
  fetch('/dochat/admin/docs/' + docId, { method: 'DELETE' })
    .then(function(res) {
      if (res.ok) {
        var row = document.getElementById('doc-row-' + docId);
        if (row) row.remove();
      } else {
        showError('Could not delete document. Please try again.');
      }
    })
    .catch(function() {
      showError('Could not reach the server. Check your connection and try again.');
    });
}

/* escapeHtml(str) — prevent XSS when building innerHTML */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* DOMContentLoaded — attach all event handlers */
document.addEventListener('DOMContentLoaded', function() {
  var dropZone = document.getElementById('drop-zone');
  var fileInput = document.getElementById('file-input');
  var browseBtn = document.getElementById('browse-btn');
  var urlForm = document.getElementById('url-form');
  var dismissError = document.getElementById('dismiss-error');
  var docTableBody = document.getElementById('doc-table-body');

  /* Drop zone drag events */
  if (dropZone) {
    dropZone.addEventListener('dragover', function(e) {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', function() {
      dropZone.classList.remove('dragover');
    });
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      var file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    });
  }

  /* Browse button click */
  if (browseBtn) {
    browseBtn.addEventListener('click', function() {
      document.getElementById('file-input').click();
    });
  }

  /* File input change */
  if (fileInput) {
    fileInput.addEventListener('change', function(e) {
      var file = e.target.files[0];
      if (file) uploadFile(file);
    });
  }

  /* URL form submit */
  if (urlForm) {
    urlForm.addEventListener('submit', function(e) {
      e.preventDefault();
      var url = document.getElementById('url-input').value.trim();
      if (url) submitUrl(url);
    });
  }

  /* Error dismiss */
  if (dismissError) {
    dismissError.addEventListener('click', function() {
      var errorBox = document.getElementById('upload-error');
      if (errorBox) errorBox.hidden = true;
      var errorText = document.getElementById('upload-error-text');
      if (errorText) errorText.textContent = '';
    });
  }

  /* Delete button delegation on table body */
  if (docTableBody) {
    docTableBody.addEventListener('click', function(e) {
      var btn = e.target.closest('.delete-btn');
      if (!btn) return;
      var docId = btn.getAttribute('data-doc-id');
      var filename = btn.getAttribute('data-filename');
      if (docId && filename) deleteDoc(docId, filename);
    });
  }
});
