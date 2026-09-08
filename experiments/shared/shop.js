"use strict";

const products = [
  { id:"digital", number:"01", name:"Digital image", price:38, image:"assets/washington-hydrographic-map.jpg", description:"A high-resolution map image for a screen, a personal archive, or your own framing.", delivery:["4000px PNG","Print-ready JPEG","Download link"] },
  { id:"motion", number:"02", name:"Moving water study", price:64, image:"assets/washington-annual-flow-poster.jpg", description:"A short animated interpretation of seasonal flow and change across your chosen place.", delivery:["Animated GIF","MP4 file","12-month cycle"] },
  { id:"print", number:"03", name:"Fine-art print", price:110, image:"assets/washington-elevation-report.jpg", description:"An archival pigment print on heavyweight cotton rag, made to live with you for years.", delivery:["18 × 24 in","Archival pigment ink","Cotton rag paper"] },
  { id:"report", number:"04", name:"Water story report", price:95, image:"assets/washington-elevation-report.jpg", description:"A researched visual report with historical context, seasonal patterns, and forecast-ready questions.", delivery:["Digital report","Historical context","Methods appendix"] }
];
const styles = [
  ["Field study", "Quiet terrain and water"], ["River portrait", "A focused water network"], ["Data atlas", "Evidence, labels, and context"]
];
const app = { product:"print", style:0, delivery:0, cart:[] };
const $ = id => document.getElementById(id);
const product = () => products.find(item => item.id === app.product);
const money = value => `$${value}`;

function renderCatalog() {
  $("productCatalog").innerHTML = products.map(item => `<article class="product ${item.id === app.product ? "selected" : ""}"><div class="product-visual"><img loading="lazy" src="${item.image}" alt="${item.name} example"><span class="product-number">${item.number} / ARTIFACT</span></div><div class="product-body"><h3>${item.name}</h3><p>${item.description}</p><span class="price">from ${money(item.price)}</span><button class="choose-product" data-product="${item.id}">Choose ${item.name}</button></div></article>`).join("");
}
function option(label, detail, active, attributes) { return `<button class="option ${active ? "active" : ""}" ${attributes}><b>${label}</b><small>${detail}</small></button>`; }
function renderChoices() {
  const item = product();
  $("artifactOptions").innerHTML = products.map(p => option(p.name, `from ${money(p.price)}`, p.id === item.id, `data-artifact="${p.id}"`)).join("");
  $("styleOptions").innerHTML = styles.map(([name, detail], index => option(name, detail, app.style === index, `data-style="${index}"`)).join(""));
  $("deliveryOptions").innerHTML = item.delivery.map((name, index) => option(name, index === 0 ? "Included with this selection" : "Available option", app.delivery === index, `data-delivery="${index}"`)).join("");
  $("selectionHelp").textContent = `${item.name} starts at ${money(item.price)}. Choose the place, visual direction, and delivery below.`;
}
function renderCart() {
  $("cartCount").textContent = app.cart.length;
  $("total").textContent = money(app.cart.reduce((sum, item) => sum + item.price, 0));
  $("reviewButton").disabled = app.cart.length === 0;
  $("cartItems").innerHTML = app.cart.length ? app.cart.map((item, index) => `<div class="cart-item"><div><strong>${item.name}</strong><small>${item.place} · ${item.style}<br>${item.delivery}</small></div><div><strong>${money(item.price)}</strong><button class="remove" data-remove="${index}">Remove</button></div></div>`).join("") : '<p class="cart-empty">Nothing has been added yet. Choose an artifact, personalize it, then add it here for review.</p>';
}
function render() { renderCatalog(); renderChoices(); renderCart(); }
function toast(message) { $("toast").textContent = message; $("toast").classList.add("show"); window.setTimeout(() => $("toast").classList.remove("show"), 2500); }
function addCurrent() {
  const item = product(); const delivery = item.delivery[app.delivery] || item.delivery[0];
  app.cart.push({ name:item.name, price:item.price, place:$("place").value, style:styles[app.style][0], delivery }); renderCart(); toast(`${item.name} added to your proposal.`);
}
document.addEventListener("click", event => {
  const choice = event.target.closest("[data-product], [data-artifact], [data-style], [data-delivery], [data-remove]");
  if (choice?.dataset.product || choice?.dataset.artifact) { app.product = choice.dataset.product || choice.dataset.artifact; app.delivery = 0; render(); document.querySelector("#make").scrollIntoView({ behavior:"smooth", block:"start" }); }
  else if (choice?.dataset.style !== undefined) { app.style = +choice.dataset.style; renderChoices(); }
  else if (choice?.dataset.delivery !== undefined) { app.delivery = +choice.dataset.delivery; renderChoices(); }
  else if (choice?.dataset.remove !== undefined) { app.cart.splice(+choice.dataset.remove, 1); renderCart(); }
});
$("cartJump").addEventListener("click", () => $("cart").scrollIntoView({ behavior:"smooth", block:"start" }));
$("reviewButton").addEventListener("click", () => toast("Proposal review will be the next checkout step."));
const addButton = document.createElement("button"); addButton.className = "primary"; addButton.textContent = "Add to proposal"; addButton.type = "button"; addButton.addEventListener("click", addCurrent); document.querySelector(".configuration").append(addButton);
render();
