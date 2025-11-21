import os
from datetime import datetime, timedelta
from typing import List, Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import TripPreference, Itinerary, ItineraryItem

app = FastAPI(title="Itinerix API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# Utilities
# -------------------------------

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # Convert datetimes to ISO strings
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    # Nested conversions
    def convert_nested(x):
        if isinstance(x, list):
            return [convert_nested(i) for i in x]
        if isinstance(x, dict):
            return {k: convert_nested(v) for k, v in x.items()}
        if isinstance(x, datetime):
            return x.isoformat()
        return x
    return convert_nested(d)


def date_diff_days(start: str, end: str) -> int:
    try:
        sd = datetime.strptime(start, "%Y-%m-%d")
        ed = datetime.strptime(end, "%Y-%m-%d")
        delta = (ed - sd).days + 1
        return max(1, delta)
    except Exception:
        return 3  # sensible default


# -------------------------------
# Simple AI-inspired generator
# -------------------------------

def pick_emoji(destination: str) -> str:
    name = destination.lower()
    if any(k in name for k in ["paris", "rome", "florence", "milan"]):
        return "🗺️"
    if any(k in name for k in ["tokyo", "kyoto", "osaka", "japan"]):
        return "🗻"
    if any(k in name for k in ["beach", "bali", "maldives", "honolulu", "miami"]):
        return "🏝️"
    if any(k in name for k in ["new york", "nyc", "los angeles", "la", "london"]):
        return "🏙️"
    return "✈️"


def generate_daily_plan(day_idx: int, prefs: TripPreference) -> List[ItineraryItem]:
    buckets = []
    interest_map = {
        "food": ("food", ["morning", "evening"]),
        "museums": ("culture", ["afternoon"]),
        "art": ("culture", ["afternoon", "evening"]),
        "nature": ("adventure", ["morning", "afternoon"]),
        "shopping": ("shopping", ["afternoon", "evening"]),
        "nightlife": ("nightlife", ["evening"]),
        "relax": ("relaxation", ["morning", "afternoon"]),
        "history": ("culture", ["morning"]),
    }

    pace_to_count = {"relaxed": 2, "balanced": 3, "packed": 4}
    count = pace_to_count.get(prefs.pace, 3)

    chosen = []
    for i in range(count):
        # Cycle through interests to diversify
        key = prefs.interests[i % max(1, len(prefs.interests))].lower() if prefs.interests else "sightseeing"
        cat, times = interest_map.get(key, ("sightseeing", ["morning", "afternoon", "evening"]))
        tod = times[i % len(times)]
        title = {
            "sightseeing": "Iconic Landmark Walk",
            "food": "Local Bites & Street Food",
            "culture": "Museum or Cultural Spot",
            "adventure": "Outdoor Adventure",
            "relaxation": "Slow Stroll & Cafe",
            "shopping": "Design + Boutique Crawl",
            "nightlife": "Evening Bars & Live Music",
            "transport": "Transfer/Check-in",
        }[cat]
        desc = f"Curated {cat} stop aligned with your mood: {', '.join(prefs.mood) or 'explore'}."
        chosen.append(ItineraryItem(day=day_idx, title=title, description=desc, category=cat, time_of_day=tod))
    return chosen


def generate_itinerary(prefs: TripPreference) -> Itinerary:
    days = date_diff_days(prefs.start_date, prefs.end_date)
    items: List[ItineraryItem] = []

    # Arrival and departure helpers
    items.append(
        ItineraryItem(
            day=1,
            title="Arrival & Check-in",
            description="Settle in and take a gentle neighborhood walk.",
            category="transport",
            time_of_day="morning",
        )
    )

    for d in range(1, days + 1):
        items.extend(generate_daily_plan(d, prefs))

    if days > 2:
        items.append(
            ItineraryItem(
                day=days,
                title="Farewell Dinner",
                description="Wrap up the trip with a memorable final meal.",
                category="food",
                time_of_day="evening",
            )
        )

    name = f"{prefs.destination}: {days} days"
    summary = (
        f"Personalized plan for {prefs.destination} over {days} days, "
        f"optimized for a {prefs.pace} pace with a {prefs.budget_level} budget."
    )

    return Itinerary(
        name=name,
        preference=prefs,
        items=items,
        summary=summary,
        destination_emoji=pick_emoji(prefs.destination),
    )


# -------------------------------
# API Routes
# -------------------------------

@app.get("/")
def read_root():
    return {"message": "Itinerix API is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from Itinerix backend!"}


class GenerateResponse(BaseModel):
    id: str
    itinerary: Dict[str, Any]


@app.post("/api/itineraries/generate", response_model=GenerateResponse)
def generate_route(prefs: TripPreference):
    try:
        itinerary = generate_itinerary(prefs)
        inserted_id = create_document("itinerary", itinerary)

        # Fetch saved doc to return consistent payload
        saved = db["itinerary"].find_one({"_id": db["itinerary"].inserted_id}) if False else None
        # If not re-querying, serialize from model
        payload = itinerary.model_dump()
        payload["created_at"] = datetime.utcnow().isoformat()
        return {"id": inserted_id, "itinerary": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itineraries")
def list_itineraries():
    try:
        cursor = db["itinerary"].find({}).sort("created_at", -1).limit(10)
        docs = [serialize_doc(d) for d in cursor]
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itineraries/{itinerary_id}")
def get_itinerary(itinerary_id: str):
    from bson import ObjectId

    try:
        doc = db["itinerary"].find_one({"_id": ObjectId(itinerary_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
