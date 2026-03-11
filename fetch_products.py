# fetch_products.py
import requests

# This file collects names of popular devices (phones + laptops)
phones = [
    "iPhone 11", "iPhone 12", "iPhone 13", "Samsung Galaxy S21", "Samsung Galaxy S22",
    "Google Pixel 5", "OnePlus 9", "Xiaomi Redmi Note 11", "Oppo Reno 8", "Vivo V27",
    "Realme 9 Pro", "Nothing Phone 1", "Asus ROG Phone 7", "Poco F4", "Nokia X30"
]

laptops = [
    "Dell Inspiron 15", "HP Pavilion 14", "Lenovo ThinkPad T14", "MacBook Air M1",
    "MacBook Pro 13", "Asus ZenBook 14", "Acer Aspire 5", "MSI Modern 15",
    "Surface Laptop 4", "Samsung Galaxy Book"
]

devices = phones + laptops

# Save all device names into a text file
with open("models_to_scrape.txt", "w", encoding="utf-8") as f:
    for item in devices:
        f.write(item + "\n")

print("✅ Done! Saved", len(devices), "device names to models_to_scrape.txt")