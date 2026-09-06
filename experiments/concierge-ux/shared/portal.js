"use strict";
document.querySelectorAll("[data-nav]").forEach(link => {
  if (link.getAttribute("href") === location.pathname.split("/").pop()) link.classList.add("active");
});

if (location.pathname.endsWith("client-request.html")) {
  const submit = document.querySelector('a[href="client-proof.html"]');
  if (submit) submit.href = "client-confirmation.html";
}
