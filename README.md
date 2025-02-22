# CrawlRouter

This is a API that is Firecrawl-compatible and integrates with Tavily, Searxng, Firecrawl, Jina, Google CSE, Scraping Bee, Scraping Ant, Markdowner and Crawl4ai.

I've developed this tool because the different searching and scraping API available don’t have the same format and are not compatible. This software helps to use the tool of your choice with a software that is compatible with Firecrawl.

It allows to rotate between providers to help staying within the rate limits.

## Prerequisites

Install the dependencies:

```bash
pip install -r requirements.txt
fastapi run app.py --reload or uvicorn app:app --reload --host 0.0.0.0
```

This will start the API server at `http://0.0.0.0:8000`.


## Environment Variables

The API relies on the following environment variables:

*   `SEARXNG_ENDPOINT`: Endpoint for Searxng. JSON needs to be activated in the formats in the search section of settings.yml : [https://docs.searxng.org/admin/engines/settings.html#search](https://docs.searxng.org/admin/settings/settings_search.html)
*   `SEARXNG_ENGINES`: see https://docs.searxng.org/dev/search_api.html
*   `SEARXNG_CATEGORIES`: see https://docs.searxng.org/dev/search_api.html
*   `SEARXNG_LANGUAGE`: see https://docs.searxng.org/dev/search_api.html

*   `FIRECRAWL_API_KEY`: API key for Firecrawl.
*   `FIRECRAWL_SEARCH_ENDPOINT`: Endpoint for Firecrawl Search API.
*   `FIRECRAWL_SCRAPE_ENDPOINT`: Endpoint for Firecrawl Scraping API.

*   `CRAWL4AI_API_KEY`: API key for Crawl4ai.
*   `CRAWL4AI_ENDPOINT`: Endpoint for Crawl4ai.
*   `CRAWL4AI_TIMEOUT`: Timeout for Crawl4ai.

*   `JINA_API_KEY`: API key for Jina.
*   `JINA_ENDPOINT`: Endpoint for Jina.

*   `MARKDOWNER_API_KEY`: API key for Markdowner.

*   `SCRAPINGANT_API_KEY`: API key for Scraping Ant.
*   `SCRAPINGANT_JS_RENDERING`: (boolean). Enable JS rendering for Scraping Ant.
  
*   `SCRAPINGBEE_API_KEY`: API key for Scrapint Bee.
*   `SCRAPINGBEE_JS_RENDERING`: (boolean). Enable JS rendering for Scraping Bee.

*   `SERPAPI_KEY`: API key for SerpAPI.

*   `TAVILY_API_KEY`: API key for Tavily.

*   `GOOGLE_CSE_KEY`: API Key for Google Custom Search Engine.
*   `GOOGLE_CSE_ID`: ID of Google Custom Search Engine.

*   `SEARCH_BACKEND`: Search endpoint default backend.
*   `SCRAPE_BACKEND`: Scrape endpoint default backend.

*   `SEARCH_BACKEND_ROTATE`: If defined, rotate randomly from the list for the search backend. Example : 'google,searxng,serpapi'
*   `SCRAPE_BACKEND_ROTATE`: If defined, rotate randomly from the list for the search backend. Example : 'crawl4ai,jina'

*   `LOG_FILE`: Path of the log file

You can also pass the API keys and endpoint via query parameters.


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
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.

*  `/search/searxng` (GET): Searxng search endpoint.
    *   `query`: Search query (required).
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.
*  `/search/firecrawl` (GET): Firecrawl search endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.
* `/search/cse` (GET): Google Custom Search Engine endpoint.
    *  `query`: Search query (required).
    *  `google_cse_id`: Google Custom Search Engine ID (optional). Can be set with environment variable.
    *  `google_cse_key`: Google Custom Search Engine Key (optional). Can be set with environment variable.
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.
*  `/search/brave` (GET): Brave Search API endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.
* `/search/serpapi` (GET): SerpAPI endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.
* `/search/tavily` (GET): Tavily endpoint.
    *   `query`: Search query (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `limit` : Number of results to return. Default is 5.
    *   `scrape` : Boolean. If true, scrape each page in the result.


### Scrape Endpoints

*   `/scrape` (GET/POST): Combined scrape endpoint.
    or `/v1/scrape`
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (optional). Can be set with environment variable.
    *   `endpoint`: endpoint (for self-hosted) (optional). Can be set with environment variable.
    *   `backend`: Scraping backend (optional, can be `jina`, `firecrawl`, `crawl4ai`, 'scrapingant', 'scrapingbee', 'markdowner' or `tavily`). Defaults to `SCRAPE_BACKEND` environment variable if not provided, otherwise to `jina`.

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
*   `/scrape/scrapingant` (GET): Scraping Ant endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (required). Can be set with environment variable.
*   `/scrape/scrapingbee` (GET): Scraping Bee endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (required). Can be set with environment variable.
*   `/scrape/markdowner` (GET): Markdowner endpoint.
    *   `url`: URL to scrape (required).
    *   `api_key`: API key (optional). Can be set with environment variable.

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

## Comparaison of API providers
### SERP API

| Provider     | Free tier    | Price                            | Link                                                                      |
|--------------|--------------|----------------------------------|---------------------------------------------------------------------------|
| Bing         | 1000 / month | $15 /1000                        | https://www.microsoft.com/en-us/bing/apis/pricing                         |
| Google       | 100 / day    | $5 / 1000                        | https://developers.google.com/custom-search/v1/overview?hl=fr             |
| Brave        | 2000 / month | $5 / 1000                        | https://api-dashboard.search.brave.com/app/subscriptions/subscribe?tab=ai |
| Tavily       | 1000 / month | $0.008 / 1                       | https://tavily.com/                                                       |
| SerpApi      | 100 / month  | $75 / 5000 / month               | https://serpapi.com/                                                      |
| Firecrawl    | 500 onetime  | $16 / 3000 / month<br>$11 / 1000 | https://www.firecrawl.dev/                                                |
| Serp.ing     | 1000 / month | $29 / 12000 / month              | https://www.serp.ing/                                                     |
| Search1API   | no           | $0.99 / 1000 / month             | https://www.search1api.com/                                               |
| Spider.cloud | $2 onetime   | $0.005 / 1                       | https://spider.cloud/                                                     |
| Brightdata   | no           | $1.5 / 1000                      | https://brightdata.fr/pricing/serp                                        |


### Scraping API

| Provider      | Free tier          | Price (for credit)     | Price for JS render | $/1k pages | Link                         |
|---------------|--------------------|------------------------|---------------------|------------|------------------------------|
| ScrapeOps     | 1 000 / month      | $9 / 25 000            | 10 credits / page   | 3.6        | https://scrapeops.io/        |
| Sraping Robot | 5000 / month       | pay as you go          | $0.0018 / page      | 1.8        | https://scrapingrobot.com/   |
| Scrappey      | 150 onetime        | pay as you go          | $0.0002 / page      | 2.0        | https://scrappey.com/        |
| Diifbot       | 10 000 / month     | $299 / 250 000 / month | 1 credits / page    | 1.2        | https://www.diffbot.com      |
| Search1API    | no                 | $0.99 / 1000 / month   | 1 credits / page    | 1.0        | https://www.search1api.com   |
| ScrapingBee   | 1000 onetime       | $49 / 150 000 / month  | 5 credits / page    | 1.6        | https://www.scrapingbee.com/ |
| ScrapingAnt   | 10 000 / month     | $19 / 100 000 / month  | 10 credits / page   | 1.9        | https://scrapingant.com/     |
| Spider.cloud  | $2                 | pay as you go          | $0.00031 / page     | 0.3        | https://spider.cloud/        |
| Tavily        | 1000 / month       | $0.008 / 1            | 5 pages / credit    | 1.6        | https://tavily.com/          |


## Docker hub image

`docker pull loorisr/crawlrouter:latest`

## Roadmap

I'am currently working on the /batch/scrape endpoint and using it for the /search endpoint when the pages needs to be scrapped.

Ideas for the future:
* add new backends: https://www.diffbot.com, https://scrappey.com/, https://www.search1api.com/, https://www.serp.ing/, https://scrapeops.io/, https://scrapingrobot.com/, Bing Search API
* complete the API implementation (scraping options) 
