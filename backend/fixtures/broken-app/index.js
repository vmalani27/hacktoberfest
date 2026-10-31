// Deliberately broken app to trigger stop-rule guardrail
console.log("Starting server...")

const express = require('express; // <--- Intentionally missing closing quote

app.listen(3000, () => {
  console.log("Listening on 3000");
});
