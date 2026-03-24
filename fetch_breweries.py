import requests
import csv
import time

API_URL = "https://api.openbrewerydb.org/v1/breweries"
OUTPUT_FILE = "breweries.csv"
PER_PAGE = 200  # max allowed by the API
TIMEOUT = 10  # seconds
MAX_RETRIES = 3


def fetch_all_breweries():
    """
    Fetch all brewery records from the configured Open Brewery DB API across paginated responses.
    
    Retrieves pages of breweries (using PER_PAGE) starting at page 1 and accumulates results until the API returns an empty page or a page with fewer than PER_PAGE items. Each page request is retried up to MAX_RETRIES on timeouts with exponential backoff between attempts.
    
    Returns:
        list[dict]: A list of brewery objects returned by the API, in the order fetched.
    
    Raises:
        requests.exceptions.Timeout: If a page request times out on the final retry.
        SystemExit: If a non-timeout request error occurs for any page (wraps the original RequestException).
    """
    breweries = []
    page = 1

    while True:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    API_URL,
                    params={"per_page": PER_PAGE, "page": page},
                    timeout=TIMEOUT,
                )
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                print(f"Page {page}: request timed out (attempt {attempt}/{MAX_RETRIES})")
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as exc:
                raise SystemExit(f"Request failed on page {page}: {exc}") from exc
        data = response.json()

        if not data:
            break

        breweries.extend(data)
        print(f"Page {page}: fetched {len(data)} breweries (total so far: {len(breweries)})")

        if len(data) < PER_PAGE:
            break

        page += 1
        time.sleep(0.2)  # be polite to the API

    return breweries


def save_to_csv(breweries, filepath):
    """
    Write a list of brewery records to a CSV file, using columns for every key present across the records.
    
    Parameters:
        breweries (list[dict]): Iterable of brewery objects (dictionaries) to write as CSV rows.
        filepath (str): Path to the output CSV file.
    
    Notes:
        - Column headers are the sorted union of all keys found in `breweries`.
        - If `breweries` is empty, the function prints "No data to save." and does not create a file.
        - On success, the function prints a message stating how many breweries were saved and the output path.
    """
    if not breweries:
        print("No data to save.")
        return

    fieldnames = sorted({k for row in breweries for k in row.keys()})

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(breweries)

    print(f"Saved {len(breweries)} breweries to {filepath}")


if __name__ == "__main__":
    breweries = fetch_all_breweries()
    save_to_csv(breweries, OUTPUT_FILE)
