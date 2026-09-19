import asyncio
import json
import os
from ev_charger import get_bangalore_chargers, Charger
import dataclasses

class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

async def main():
    print("Fetching chargers...")
    chargers = await get_bangalore_chargers()
    print(f"Fetched {len(chargers)} chargers.")
    
    out_path = os.path.join(os.path.dirname(__file__), "..", "geojson", "bangalore_chargers.json")
    with open(out_path, "w") as f:
        json.dump(chargers, f, cls=EnhancedJSONEncoder, indent=2)
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
