import asyncio
from main import app
from httpx import AsyncClient, ASGITransport

async def test():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        req = {
            "origin": {"lat": 12.9716, "lng": 77.5946},
            "destination": {"lat": 12.9650, "lng": 77.5938}, # Much shorter
            "carrier": "composite",
            "persona": "safe_commute",
            "alpha": 0.15,
            "weather_scenario": "clear",
            "timestamp": "2026-09-18T10:00:00Z"
        }
        res = await ac.post("/api/route/score", json=req)
        data = res.json()
        print("Status:", res.status_code)
        if "routes" in data:
            for i, r in enumerate(data["routes"]):
                val = r.get("safety_explanation", "MISSING")
                print(f"Route {i}: explanation = {val!r}")
        else:
            print("No routes in response:", data)

asyncio.run(test())
