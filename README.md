# CrawlRouter

This is a API that is Firecrawl-compatible and integrates with Tavily, Searxng, Firecrawl, Jina, Google CSE and Crawl4ai.

I've developed this tool because the different searching and scraping API available don’t have the same format and are not compatible. This software helps to use the tool of your choice with a software that is compatible with Firecrawl.

## Prerequisites

*   Python 3.7+
*   FastAPI
*   httpx
*   uvicorn (for running the server)

Install the dependencies:

```bash
pip install fastapi httpx uvicorn
```

## Environment Variables

The API relies on the following environment variables:

*   `SEARXNG_ENDPOINT`: Endpoint for Searxng. JSON needs to be activated in the formats in the search section of settings.yml : [https://docs.searxng.org/admin/engines/settings.html#search](https://docs.searxng.org/admin/settings/settings_search.html)

*   `FIRECRAWL_API_KEY`: API key for Firecrawl.
*   `FIRECRAWL_SEARCH_ENDPOINT`: Endpoint for Firecrawl Search API.
*   `FIRECRAWL_SCRAPE_ENDPOINT`: Endpoint for Firecrawl Scraping API.

*   `CRAWL4AI_API_KEY`: API key for Crawl4ai.
*   `CRAWL4AI_ENDPOINT`: Endpoint for Crawl4ai.
*   `CRAWL4AI_TIMEOUT`: Timeout for Crawl4ai.

*   `JINA_API_KEY`: API key for Jina.
*   `JINA_ENDPOINT`: Endpoint for Jina.

*   `SERPAPI_KEY`: API key for SerpAPI.

*   `TAVILY_API_KEY`: API key for Tavily.

*   `GOOGLE_CSE_KEY`: API Key for Google Custom Search Engine.
*   `GOOGLE_CSE_ID`: ID of Google Custom Search Engine.

*   `SEARCH_BACKEND`: Search endpoint default backend.
*   `SCRAPE_BACKEND`: Scrape endpoint default backend.


You can also pass the API keys and endpoint via query parameters.

## Running the API

```bash
uvicorn app:app --reload --host 0.0.0.0
```

This will start the API server at `http://0.0.0.0:8000`.

## Endpoints

### Documentation Endpoints

*   `/` or `/docs` (GET): API documentation in Swagger UI
*   `/redoc` (GET): API documentation in ReDoc

### Search Endpoints

*   `/search` (GET/POST): Combined search endpoint.
    or `/v1/search`
    *   `query`: Search query (required).
    *   `backend`: Search backend (optional, can be `google`, `searxng`, `brave`, `firecrawl`, `serpapi` or `tavily`). Defaults to `SEARCH_BACKEND` environment variable if not provided.
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
    *  `google_cse_id`: Google Custom Search Engine ID (optional). Can be set with environment variable.
    *  `google_cse_key`: Google Custom Search Engine Key (optional). Can be set with environment variable.

*  `/search/searxng` (GET): Searxng search endpoint.
    *   `query`: Search query (required).
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
*  `/search/firecrawl` (GET): Firecrawl search endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
* `/search/cse` (GET): Google Custom Search Engine endpoint.
    *  `query`: Search query (required).
    *  `google_cse_id`: Google Custom Search Engine ID (optional). Can be set with environment variable.
    *  `google_cse_key`: Google Custom Search Engine Key (optional). Can be set with environment variable.
*  `/search/brave` (GET): Brave Search API endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
* `/search/serpapi` (GET): SerpAPI endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
* `/search/tavily` (GET): Tavily endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.


### Scrape Endpoints

*   `/scrape` (GET/POST): Combined scrape endpoint.
    or `/v1/scrape`
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
    *   `backend`: Scraping backend (optional, can be `jina`, `firecrawl`, `crawl4ai` or `tavily`). Defaults to `SCRAPE_BACKEND` environment variable if not provided, otherwise to `jina`.

*   `/scrape/firecrawl` (GET): Firecrawl scrape endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
*   `/scrape/crawl4ai` (GET): Crawl4ai scrape endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
*   `/scrape/jina` (GET): Jina Reader endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
*   `/scrape/tavily` (GET): Tavily endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (required). Can be set with environment variable.

## Example Usage

```
http://127.0.0.1:8000/scrape?url=https://www.wikipedia.org&backend=jina
```
```
http://127.0.0.1:8000/search?query=awesome scraping API&backend=searxng&endpoint=https://search.url4irl.com/
```

## Self-hostable tools
* Jina Reader: https://github.com/intergalacticalvariable/reader
* Firecrawl: https://github.com/mendableai/firecrawl or https://github.com/devflowinc/firecrawl-simple/
* SearXNG: https://github.com/searxng/searxng
* Crawl4AI https://github.com/unclecode/crawl4ai

## Docker hub image

`docker pull loorisr/crawlrouter:latest`

## Roadmap

I'am currently working on the /batch/scrape endpoint and using it for the /search endpoint when the pages needs to be scrapped.

Ideas for the future:
* add new backends: [ScrapingAnt](https://scrapingant.com/), [ScrapingBee](https://www.scrapingbee.com/), [Markdowner](https://github.com/supermemoryai/markdowner), Bing Search API
* complete the API implementation (scraping options) 
