fetch("http://localhost:8002/api/run/start", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    run_id: "test-race-1",
    ticker: "MU",
    date_from: "2026-02-09",
    date_to: "2026-02-13",
    strategy_api_url: "http://localhost:8001"
  })
}).then(r => r.json()).then(console.log);
fetch("http://localhost:8002/api/run/start", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    run_id: "test-race-1",
    ticker: "MU",
    date_from: "2026-02-09",
    date_to: "2026-02-13",
    strategy_api_url: "http://localhost:8001"
  })
}).then(r => r.json()).then(console.log);
