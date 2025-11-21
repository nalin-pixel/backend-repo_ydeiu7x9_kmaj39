"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# ----------------------------
# Itinerix Collections Schemas
# ----------------------------

class TripPreference(BaseModel):
    """Preferences provided by the user to generate an itinerary.
    Collection name: "trippreference" (lowercase of class name)
    """
    destination: str = Field(..., description="Destination city or region")
    start_date: str = Field(..., description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Trip end date (YYYY-MM-DD)")
    travelers: int = Field(1, ge=1, le=12, description="Number of travelers")
    budget_level: Literal["shoestring", "moderate", "luxury"] = Field(
        "moderate", description="Budget preference"
    )
    pace: Literal["relaxed", "balanced", "packed"] = Field(
        "balanced", description="Daily activity pace"
    )
    mood: List[str] = Field(default_factory=list, description="Overall mood keywords")
    interests: List[str] = Field(default_factory=list, description="Interest tags like food, museums, nature")
    notes: Optional[str] = Field(None, description="Additional notes or constraints")

class ItineraryItem(BaseModel):
    """One activity or plan segment inside an itinerary."""
    day: int = Field(..., ge=1, description="Day number in the trip")
    title: str
    description: str
    category: Literal[
        "sightseeing",
        "food",
        "culture",
        "adventure",
        "relaxation",
        "shopping",
        "nightlife",
        "transport"
    ] = "sightseeing"
    time_of_day: Literal["morning", "afternoon", "evening", "flex"] = "flex"
    location: Optional[str] = None
    cost_estimate: Optional[float] = Field(None, ge=0)

class Itinerary(BaseModel):
    """Generated itinerary document.
    Collection name: "itinerary"
    """
    name: str = Field(..., description="Human-friendly title for this itinerary")
    preference: TripPreference
    items: List[ItineraryItem] = Field(default_factory=list)
    summary: Optional[str] = Field(None, description="Short overview of the trip")
    destination_emoji: Optional[str] = None

# Retain example schemas for reference (not used by the app but harmless)
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
