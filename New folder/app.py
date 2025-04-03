from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/outline")
async def get_country_outline(country: str = Query(..., description="Name of the country")):
    """
    API endpoint to fetch the Wikipedia page of a country and return a Markdown outline.
    :param country: Name of the country (query parameter).
    :return: Markdown-formatted outline of the Wikipedia page.
    """
    # Fetch the Wikipedia page for the given country
    wikipedia_url = f"https://en.wikipedia.org/wiki/{country.replace(' ', '_')}"
    response = requests.get(wikipedia_url)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Wikipedia page for '{country}' not found.")

    # Parse the HTML content of the Wikipedia page
    soup = BeautifulSoup(response.content, "html.parser")

    # Extract headings (H1 to H6) and maintain hierarchy
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    
    if not headings:
        raise HTTPException(status_code=404, detail=f"No headings found on the Wikipedia page for '{country}'.")

    # Generate Markdown outline
    markdown_outline = ["## Contents", f"# {country}"]
    
    for heading in headings:
        level = int(heading.name[1])  # Extract level from tag name (e.g., h2 -> 2)
        text = heading.get_text(strip=True)
        markdown_outline.append(f"{'#' * level} {text}")

    # Join the Markdown lines into a single string
    markdown_result = "\n\n".join(markdown_outline)

    return {"markdown": markdown_result}
