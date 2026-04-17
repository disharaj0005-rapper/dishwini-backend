from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, products, collections, orders, cart, users, contacts, subscriptions, filters

settings = get_settings()

app = FastAPI(
    title="Dishwini Fashion Store API",
    description="Backend API for Dishwini Fashion E-Commerce Platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        settings.ADMIN_URL,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(collections.router, prefix="/collections", tags=["Collections"])
app.include_router(cart.router, prefix="/cart", tags=["Cart"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])

app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
app.include_router(filters.router, prefix="/filters", tags=["Filters"])


@app.get("/", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "Dishwini Fashion Store API",
        "version": "1.0.0"
    }
