// Error message extraction for API responses
export function getErrorMessage(error){
    if (typeof error.detail === 'string'){
        return error.detail;
    } else if (Array.isArray(error.detail)){
        return error.detail.map((err) => err.msg).join(" .")
    }
}

// Show a Bootstrap modal by ID
export function showModal(modalId) {
  const modal = bootstrap.Modal.getOrCreateInstance(
    document.getElementById(modalId),
  );
  modal.show();
  return modal; 
}

// Hide a Bootstrap modal by ID
export function hideModal(modalId) {
  const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
  if (modal) modal.hide();
}

// XSS prevention for dynamic content insertion
export function escapeHtml(text){
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}  // The function above is used to prevent cross site attack, which is when someone puts malicious code in the, let's say, the title of the page, this function helps us escape the code , to plain text I think

// Date formatting to match server's strftime("%B %d, %Y")
export function formatDate(dateString){
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US",{
    year: "numeric",
    month: "long",
    day: "2-digit",
  });
}