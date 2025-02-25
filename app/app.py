from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, NonNegativeInt, PositiveInt, HttpUrl, root_validator, Field
from typing import Union, List, Optional, Literal
from markdownify import markdownify as md
import os
import time
import sys
import httpx
import asyncio
import random
import csv
from datetime import datetime

FIRECRAWL_SEARCH_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/search"
FIRECRAWL_SCRAPE_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_BATCH_SCRAPE_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/batch/scrape"
FIRECRAWL_DEEP_RESEARCH_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/deep-research"
FIRECRAWL_EXTRACT_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/extract"
JINA_ENDPOINT_DEFAULT = "https://r.jina.ai/"

CRAWL4AI_TIMEOUT = (int)(os.getenv("CRAWL4AI_TIMEOUT", 30))
HTTP_TIMEOUT = (int)(os.getenv("HTTP_TIMEOUT", 30))

SEARCH_BACKEND = os.getenv("SEARCH_BACKEND")
SCRAPE_BACKEND = os.getenv("SCRAPE_BACKEND")

SEARCH_BACKEND_ROTATE = os.getenv("SEARCH_BACKEND_ROTATE")
SCRAPE_BACKEND_ROTATE = os.getenv("SCRAPE_BACKEND_ROTATE")

FIRECRAWL_DEEP_RESEARCH_ENDPOINT = os.getenv("FIRECRAWL_DEEP_RESEARCH_ENDPOINT")

SEARCH_RESULT_NUMBER_DEFAULT = 5

SCRAPINGANT_JS_RENDERING = os.getenv("SCRAPINGANT_JS_RENDERING", 'False').lower() in ('true', '1', 't')
SCRAPINGBEE_JS_RENDERING = os.getenv("SCRAPINGBEE_JS_RENDERING", 'False').lower() in ('true', '1', 't')

SEARXNG_ENGINES = os.getenv("SEARXNG_ENGINES")
SEARXNG_CATEGORIES = os.getenv("SEARXNG_CATEGORIES")
SEARXNG_LANGUAGE = os.getenv("SEARXNG_LANGUAGE")

LOG_FILE = os.getenv("LOG_FILE")

last_search_backend = None # to rotate search engine
last_scrape_backend = None # to rotate scrape engine

app = FastAPI(    title="CrawlRouter",
   # description=description,
    summary="Unified API for Searching and Scraping",
    version="0.1.2",
    contact={
        "name": "loorisr",
        "url": "https://github.com/loorisr/crawlrouter"
    },
    license_info={
        "name": "GNU Affero General Public License v3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
    },)

templates = Jinja2Templates(directory="templates")

def log_request(type, url_or_query, backend, endpoint, size, execution_time):
    if LOG_FILE:
        try:
            with open(LOG_FILE, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0: # Write header if file is empty
                    writer.writerow(['Date/Time', 'Type', 'URL/Query', 'Backend', 'Endpoint', 'Size', 'API execution_time'])
                if isinstance(url_or_query, str):
                    writer.writerow([datetime.now(), type, url_or_query, backend, endpoint, size, round(execution_time, 3)])
                else:
                    for item in url_or_query:
                        writer.writerow([datetime.now(), type, item, backend, endpoint, size, round(execution_time, 3)])
        except Exception as e:
            print (f"Error during logging: {e}")

@app.get("/")
async def read_home_ui(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    raise HTTPException(status_code=404, detail=f"Not found")

@app.get("/ui/scrape", response_class=HTMLResponse)
async def read_scrape_ui(request: Request):
    return templates.TemplateResponse("scrape-ui.html", {"request": request})

@app.get("/ui/deep-research", response_class=HTMLResponse)
async def read_deep_research_ui(request: Request):
    return templates.TemplateResponse("deep-research-ui.html", {"request": request})

@app.get("/ui/extract", response_class=HTMLResponse)
async def read_extract_ui(request: Request):
    return templates.TemplateResponse("extract-ui.html", {"request": request})

# Function to get API key from query or environment variables
def get_api_key(query_key: Optional[str], env_key: str) -> str:
    if query_key:
        return query_key
    api_key = os.environ.get(env_key)
    if not api_key:
        raise HTTPException(status_code=500, detail=f"Missing API key. Provide in query or set environment variable {env_key}")
    return api_key


# Function to get endpoint from query or environment variables
def get_endpoint(query_endpoint: Optional[str], env_key: str, default_endpoint= None) -> str:
    if query_endpoint:
        return query_endpoint
    endpoint = os.environ.get(env_key)
    if endpoint:
        return endpoint
    else:
        return default_endpoint

async def make_request(url: str, headers: dict = None, params: dict = None, method: str = "GET"):
    async with httpx.AsyncClient() as client:
        try:
            if method == "POST":
                response = await client.post(url, headers=headers, json=params, timeout=HTTP_TIMEOUT)
            else:
                response = await client.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


def combined_search_scrape(search_result, scrapped_data):
    # Create a dictionary from the scrapped array for quick lookup
    scrapped_dict = {item['metadata']['url']: item['markdown'] for item in scrapped_data}

    # Combine the data
    combined_data = []
    for item in search_result['data']:
        url = item['url']
        if url in scrapped_dict:
            # Merge the data if the URL exists in both arrays
            combined_item = item.copy()
            combined_item['markdown'] = scrapped_dict[url]
            combined_data.append(combined_item)

    return combined_data

# SearXNG search function
async def searxng_search(query: str, limit, scrape):
   # api_key = get_api_key(api_key, "SEARXNG_API_KEY")
    startTime = time.time()
    endpoint = get_endpoint(None, "SEARXNG_ENDPOINT")
    if not endpoint:
        raise HTTPException(status_code=500, detail="Missing Searxng endpoint. Provide in query or set environment variable SEARXNG_ENDPOINT")
    endpoint = endpoint.rstrip('/')
    url = f"{endpoint}/search"
    params = {"q": query, "format": "json"}

    if SEARXNG_ENGINES:
        params.update({"engines": SEARXNG_ENGINES})

    if SEARXNG_CATEGORIES:
        params.update({"categories": SEARXNG_CATEGORIES})

    if SEARXNG_LANGUAGE:
        params.update({"language": SEARXNG_LANGUAGE})
    
    headers = {"Accept": "text/html", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0", "Accept-Language": "en,fr", "Accept-Encoding": "gzip,deflate"}

    print(f"Searching {query} with searxng on {endpoint}")
    result = await make_request(url, params=params, headers=headers)
    result['backend'] = "searxng"
    result['data'] = result['results']
    result['success'] = True


    result['data'] = result['data'][:limit]

    for res in result['data']:
        res['description'] = res['content']
        del res['content']
        del res['engine']
        del res['parsed_url']
        del res['positions']
        del res['score']
        del res['category']
        del res['template']
        if 'thumbnail' in res: del res['thumbnail']
        del res['engines']
        #if scrape:
            #scrapped_page = await scrape_get(url=res['url'], backend=None, api_key=None, endpoint=None)
            #res['markdown'] = scrapped_page['data']['markdown']
    del result['results']
    del result['suggestions']
    del result['infoboxes']
    del result['answers']
    del result['corrections']
    del result['query']
    del result['unresponsive_engines']
    del result['number_of_results']
    #return result

    if scrape:
        all_urls = [item['url'] for item in result['data']]
        scrapped_page = await batch_scrape_get(urls=all_urls, backend=None, api_key=None, endpoint=None)
        result['data'] = combined_search_scrape(result, scrapped_page['data'])
    
    endTime = time.time()
    log_request("search", query, result['backend'], endpoint, limit, endTime-startTime)
    return result

# Firecrawl scrape
async def firecrawl_scrape(url: str):
    startTime = time.time()
    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    endpoint = get_endpoint(None, "FIRECRAWL_SCRAPE_ENDPOINT", FIRECRAWL_SCRAPE_ENDPOINT_DEFAULT)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"url": url}
    print(f"Scraping {url} with Firecrawl on {endpoint}")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['backend'] = "firecrawl"

    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result


# Scraping Ant scrape
async def scrapingant_scrape(url: str):
    startTime = time.time()
    api_key = get_api_key(None, "SCRAPINGANT_API_KEY")
    endpoint = "https://api.scrapingant.com/v2/markdown"
    headers = {"Content-Type": "application/json"}
    params = {"url": url, "x-api-key": api_key, "return_page_source": not SCRAPINGANT_JS_RENDERING}
    print(f"Scraping {url} with Scraping Ant")
    result = {}
    result['data'] = await make_request(endpoint, params=params, headers=headers, method="GET")
    result['metadata'] = {}
    result['metadata']['url']  = result['data']['url'] 
    del result['data']['url'] 
    result['backend'] = "scrapingant"

    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result

# Scraping Bee scrape
async def scrapingbee_scrape(url: str):
    startTime = time.time()
    api_key = get_api_key(None, "SCRAPINGBEE_API_KEY")
    endpoint = "https://app.scrapingbee.com/api/v1"
    headers = {"Content-Type": "application/json"}
    params = {"url": url, "api_key": api_key, "render_js": SCRAPINGBEE_JS_RENDERING, "json_response": True}
    print(f"Scraping {url} with Scraping Bee")
    scrapped_page = await make_request(endpoint, params=params, headers=headers, method="GET")
    result = {}
    result['data'] = {}
    #result['data']['html'] = scrapped_page['body']
    result['data']['markdown'] = md(scrapped_page['body'])
    result['metadata'] = {} 
    result['metadata']['url']  = url
    result['backend'] = "scrapingbee"

    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result

# Markdowner scrape
async def markdowner_scrape(url: str):
    startTime = time.time()
    api_key = os.environ.get("MARKDOWNER_API_KEY") 
    endpoint = "https://md.dhr.wtf/"
    headers = {"Content-Type": "application/json"}

    if api_key:
        headers.update({"Authorization": f"Bearer {api_key}"})

    params = {"url": url}
    print(f"Scraping {url} with Markdowner")


    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(endpoint, headers=headers, params=params, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            scrapped_page = response.text
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    result = {}
    result['data'] = {}
    result['data']['markdown'] = scrapped_page
    result['metadata'] = {} 
    result['metadata']['url']  = url
    result['backend'] = "markdowner"

    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result

# Firecrawl batch scrape
async def firecrawl_batch_scrape(urls: list[str]):
    startTime = time.time()
    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    endpoint = get_endpoint(None, "FIRECRAWL_BATCH_SCRAPE_ENDPOINT", FIRECRAWL_BATCH_SCRAPE_ENDPOINT_DEFAULT)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"urls": urls}
    print(f"Scraping {urls} with Firecrawl on {endpoint}")

    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result_url = result['url']
    result_url = result_url.replace('https','http')
    print(result_url)
    #result_url['backend'] = "firecrawl"

    # Poll for result
    timeout = 60
    start_time = time.time()
    while True:
         if time.time() - start_time > timeout:
             #raise TimeoutError(f"Task {task_id} timeout")
             raise HTTPException(status_code=400, detail="Timeout exceeded")

         result = await make_request(result_url, params=body, headers=headers, method="GET")

         if result["status"] == "completed":
            result['backend'] = "firecrawl"
            endTime = time.time()
            log_request("scrape", urls, result['backend'], endpoint, len(result), endTime-startTime)
            return result
             
         time.sleep(1)
    
    

# Tavily scrape
async def tavily_scrape(url: str, api_key: Optional[str] = Query(None)):
    startTime = time.time()
    api_key = get_api_key(None, "TAVILY_API_KEY")
    endpoint = "https://api.tavily.com/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"urls": url}
    print(f"Scraping {url} with Tavily")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['backend'] = "tavily"
    result['data'] = {}
    if result['results']:
        result['data']['markdown'] = result['results'][0]['raw_content']
        result['data']['metadata'] = {}
        result['data']['metadata']['url'] = result['results'][0]['url'] 
        del result['results']
    else:
        result['success'] = "false"

    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result



# Tavily batch scrape
async def tavily_batch_scrape(urls: list[str]):
    startTime = time.time()
    api_key = get_api_key(None, "TAVILY_API_KEY")
    endpoint = "https://api.tavily.com/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"urls": urls}
    print(f"Scraping {urls} with Tavily")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")

    print(result)
    
    cleaned_result = {}
    cleaned_result['backend'] = "tavily"
    cleaned_result['data'] = []

    for res in result['results']:
        cleaned_1result = {}
        cleaned_1result['markdown'] = res['raw_content'] 
        cleaned_1result['metadata'] = {}
        cleaned_1result['metadata']['url'] = res['url'] 

        cleaned_result['data'].append(cleaned_1result)
        # cleaned_result['data']['metadata']['title'] = result['result']['title'] 
    result = cleaned_result
    endTime = time.time()
    log_request("scrape", urls, cleaned_result['backend'], endpoint, 0, endTime-startTime)
    return result



# Crawl4ai scrape
async def crawl4ai_scrape(url: str):
    startTime = time.time()
    api_key = get_api_key(None, "CRAWL4AI_API_KEY")
    params = {"urls": url}
    endpoint = get_endpoint(None, "CRAWL4AI_ENDPOINT")
    endpoint = endpoint.rstrip('/')
    #query_url = f"{endpoint}/crawl"  ## asynchronous
    query_url = f"{endpoint}/crawl_sync"  ## synchronous
    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"Scraping {url} with Crawl4AI on {endpoint}")

    result = await make_request(query_url, headers=headers, params=params, method="POST")
    if result["status"] == "completed":
        result['backend'] = "crawl4ai"
        result['data'] = result['result']
        result['success'] = result['data']['success']
        result['data']['metadata']['statusCode'] = result['data']['status_code'] 
        del result['result']
        del result['status']
        #del result['created_at']
        del result['data']['response_headers']
        del result['data']['markdown_v2']
        del result['data']['media']
        del result['data']['links']
        del result['data']['html']
        del result['data']['cleaned_html']
        del result['data']['fit_html']
        del result['data']['fit_markdown']
        del result['data']['success']
        del result['data']['status_code'] 
         
        endTime = time.time()
        log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
        return result       


# Crawl4ai batch scrape
async def crawl4ai_batch_scrape(urls: list[str]):
    startTime = time.time()
    api_key = get_api_key(None, "CRAWL4AI_API_KEY")
    params = {"urls": urls}
    endpoint = get_endpoint(None, "CRAWL4AI_ENDPOINT")
    endpoint = endpoint.rstrip('/')
    query_url = f"{endpoint}/crawl_sync"  ## synchronous
    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"Scraping {urls} with Crawl4AI on {endpoint}")

    result = await make_request(query_url, headers=headers, params=params, method="POST")
    cleaned_result = {}
    cleaned_result['backend'] = "crawl4ai"
    cleaned_result['data'] = []

    if result["status"] == "completed":
        for res in result['results']:
            cleaned_1result = {}
            cleaned_1result['markdown'] = res['markdown'] 
            cleaned_1result['metadata'] = res['metadata'] 
            cleaned_1result['metadata']['statusCode'] = res['status_code'] 
            cleaned_1result['metadata']['url'] = res['url'] 

            cleaned_result['data'].append(cleaned_1result)
            # cleaned_result['data']['metadata']['title'] = result['result']['title'] 

    endTime = time.time()
    log_request("scrape", urls, cleaned_result['backend'], endpoint, len(result), endTime-startTime)
    return cleaned_result      



# patchright-scrape-api scrape
async def patchright_scrape(url: str):
    startTime = time.time()
    endpoint = get_endpoint(None, "PATCHRIGHT_SCRAPE_ENDPOINT")
    body = {"url": url}
    print(f"Scraping {url} with Patchright on {endpoint}")
    result = await make_request(endpoint, params=body, headers=None, method="POST")

    cleaned_result = {}
    cleaned_result['backend'] = "patchright"
    cleaned_result['data'] = {}
    cleaned_result['data']['rawHtml'] = result['content']

    result = cleaned_result
    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result


# Google CSE search
async def google_cse_search(query: str, limit, scrape):
    startTime = time.time()
    google_cse_id = get_api_key(None, "GOOGLE_CSE_ID") 
    google_cse_key = get_api_key(None, "GOOGLE_CSE_KEY")

    num = limit

    endpoint = "https://customsearch.googleapis.com/customsearch/v1"
    params = {"q": query, "cx": google_cse_id, "key": google_cse_key, "num": num}
    print(f"Searching {query} with Google")
    result = await make_request(endpoint, params=params)
    result["backend"] = "google"
    result['data'] = result['items']
    result['success'] = True
    for res in result['data']:
        res['description'] = res['snippet']
        res['url'] = res['link']
        del res['htmlTitle']
        del res['displayLink']
        del res['htmlFormattedUrl']
        del res['formattedUrl']
        del res['htmlSnippet']
        del res['snippet']
        if 'pagemap' in res: del res['pagemap']
        del res['link']
        del res['kind']
    del result['items']
    del result['kind']
    del result['url']
    del result['queries']
    del result['searchInformation']
    del result['context']

    if scrape:
        all_urls = [item['url'] for item in result['data']]
        scrapped_page = await batch_scrape_get(urls=all_urls, backend=None, api_key=None, endpoint=None)
        result['data'] = combined_search_scrape(result, scrapped_page['data'])

    endTime = time.time()
    log_request("search", query, result['backend'], endpoint, len(result), endTime-startTime)
    return result  


# BRAVE Search API search
async def brave_search(query: str, limit, scrape):
    startTime = time.time()
    api_key = get_api_key(None, "BRAVE_API_KEY")
    endpoint = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": api_key, "Accept-Encoding": "gzip", "Accept": "application/json"}
    params = {"q": query}
    print(f"Searching {query} with Brave")
    result = await make_request(endpoint, params=params, headers=headers)
    result['backend'] = "brave"
    
    endTime = time.time()
    log_request("search", query, result['backend'], endpoint, len(result), endTime-startTime)
    return result  



# Firecrawl Search
async def firecrawl_search(query: str, limit, scrape):
    startTime = time.time()
    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    endpoint = get_endpoint(None, "FIRECRAWL_SEARCH_ENDPOINT", FIRECRAWL_SEARCH_ENDPOINT_DEFAULT)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    number_of_results = limit

    body = {"query": query}
    if scrape:
        body["scrapeOptions"] = {}
        body["scrapeOptions"]["formats"] = ["markdown"]
        
    print(f"Searching {query} with Firecrawl on {endpoint}")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['data'] = result['data'][:number_of_results]
    result['backend'] = "firecrawl"

    endTime = time.time()
    log_request("search", query, result['backend'], endpoint, len(result), endTime-startTime)
    return result  


# SerpAPI search
async def serpapi_search(query: str, limit, scrape):
    startTime = time.time()
    api_key = get_api_key(None, "SERPAPI_KEY")
    endpoint = "https://serpapi.com/search"
    
    num = limit

    params = {"q": query, "api_key": api_key, "num": num}
    print(f"Searching {query} with SerpAPI")
    result = await make_request(endpoint, params=params)
    result['backend'] = "serpapi"

    del result['search_metadata']
    del result['search_parameters']
    del result['search_information']
    if 'knowledge_graph' in result: del result['knowledge_graph']
    if 'related_questions' in result: del result['related_questions']
    if 'related_searches' in result: del result['related_searches']
    if 'answer_box' in result: del result['answer_box']
    if 'top_stories' in result: del result['top_stories']
    if 'top_stories_link' in result: del result['top_stories_link']
    if 'top_stories_serpapi_link' in result: del result['top_stories_serpapi_link']
    if 'inline_images' in result: del result['inline_images']
    del result['pagination']
    del result['serpapi_pagination']
    result['data'] = result['organic_results']

    for res in result['data']:
        res['description'] = res['snippet']
        res['url'] = res['link']
        del res['position']
        del res['link']
        if 'redirect_link' in res: del res['redirect_link']
        if 'displayed_link' in res: del res['displayed_link']
        if 'favicon' in res: del res['favicon']
        del res['snippet']
        if 'snippet_highlighted_words' in res: del res['snippet_highlighted_words']
        if 'source' in res: del res['source']
        if scrape:
            scrapped_page = await scrape_get(url=res['url'], backend=None, api_key=None, endpoint=None)
            res['markdown'] = scrapped_page['data']['markdown']
    del result['organic_results']
    result['success'] =  True

    endTime = time.time()
    log_request("search", query, result['backend'], endpoint, len(result), endTime-startTime)


    if scrape:
        all_urls = [item['url'] for item in result['data']]
        scrapped_page = await batch_scrape_get(urls=all_urls, backend=None, api_key=None, endpoint=None)
        result['data'] = combined_search_scrape(result, scrapped_page['data'])

    return result

# Tavily search
async def tavily_search(query: str, limit, scrape):
    startTime = time.time()
    api_key = get_api_key(None, "TAVILY_API_KEY")
    endpoint = "https://api.tavily.com/search"

    max_results = limit
    
    body = {"query": query, "max_results": max_results}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    print(f"Searching {query} with tavily")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['backend'] = "tavily"
    result['data'] = result['results']
    result['success'] = True
    for res in result['data']:
        res['description'] = res['content']
        del res['score']
        del res['raw_content']
        del res['content']
        if scrape:
            all_urls = [item['url'] for item in result['data']]
            #scrapped_page = await scrape_get(url=res['url'], backend=None, api_key=None, endpoint=None)
            scrapped_page = await batch_scrape_get(urls=all_urls, backend=None, api_key=None, endpoint=None)
            res['markdown'] = scrapped_page['data']['markdown']
    del result['results']
    del result['response_time']
    del result['images']
    del result['answer']
    del result['query']
    del result['follow_up_questions']

    endTime = time.time()
    log_request("search", query, result['backend'], endpoint, len(result), endTime-startTime)
    return result

# Jina Reader scrape
async def jina_reader_scrape(url: str):
    startTime = time.time()
    api_key = os.environ.get("JINA_API_KEY") 
    endpoint = get_endpoint(None, "JINA_ENDPOINT", JINA_ENDPOINT_DEFAULT)
    print(f"Scraping {url} with Jina on {endpoint}")
    headers = {"Accept": "application/json"}
    if api_key:
        headers.update({"Authorization": f"Bearer {api_key}"})
    url = f"{endpoint.rstrip('/')}/{url}"
    result = await make_request(url, headers=headers)
    result["backend"] = "Jina"

    result['data']['markdown'] = result['data']['content']
    result['data']['metadata']= {}
    result['data']['metadata']['title'] = result['data']['title']
    result['data']['metadata']['url'] = result['data']['url']
    result['data']['metadata']['statusCode'] = result['code']
    del result['data']['content']
    del result['data']['url']
    del result['data']['title']
    del result['code']
    del result['status']

    endTime = time.time()
    log_request("scrape", url, result['backend'], endpoint, len(result), endTime-startTime)
    return result



######### Scrape endpoint


class FirecrawlScapeModel(BaseModel):
    url: HttpUrl
    formats: list[Literal["markdown", "html", "rawHtml", "links", "screenshot", "screenshot@fullPage", "json"]] = ["markdown"]
    onlyMainContent: bool = True
    includeTags: list[str] = None
    excludeTags: list[str] = None
    headers: dict = None
    waitFor: NonNegativeInt = 0
    mobile: bool = False
    skipTlsVerification: bool = False
    timeout: NonNegativeInt = 30000
    jsonOptions: dict = None
    actions: list[dict] = None
    location: dict = {"country": "US", "languages":""}
    removeBase64Images: bool = False
    blockAds: bool = True
    proxy: Literal["basic", "stealth"] = None


# Handle Firecrawl compatible endpoint
@app.post("/v1/scrape")
async def scrape_post(
    body: FirecrawlScapeModel,
    backend: Optional[str] = Query(None, description="Backend to use (optional)"),
    ):
    url = str(body.url)
    
    return await scrape_single(url, backend)


class PlaywrightServiceModel(BaseModel):
    url: HttpUrl = None
    wait_after_load: Optional[NonNegativeInt] = 0
    timeout: Optional[NonNegativeInt] = 15000
    headers: Optional[dict] = None

# Handle playwright-service compatible endpoint
@app.post("/scrape")
async def scrape_page_endpoint(body: PlaywrightServiceModel):
    url = str(body.url)

    scrapped_result = await scrape_single(url, None)

    result = {}
    result['content'] = scrapped_result['data']['markdown'] # should be rawHtml, needs to update scrape_single to take more parameters
    result['pageStatusCode'] = scrapped_result['data']['metadata']['statusCode'] 
    
    return result
    
async def scrape_single(url: str, backend):
    if not backend:
        backend = SCRAPE_BACKEND

    if not backend:
        backend = "jina"  # jina can be used without an API key

    options = backend.split(',')
    if SCRAPE_BACKEND_ROTATE == "random":
        # Split the string by comma to get a list of options
        # Randomly select one of the options
        backend = random.choice(options)
    #elif SCRAPE_BACKEND_ROTATE == "sequential":
    else:
        global last_scrape_backend 
        if last_scrape_backend != None:
            last_scrape_backend = (last_scrape_backend + 1) % len(options)
            backend = options[last_scrape_backend]

        else:
            last_scrape_backend = 0
            backend = options[last_scrape_backend]

    if backend not in ["jina", "firecrawl", "crawl4ai", "tavily", "scrapingant", "scrapingbee", "markdowner", "patchright"]:
        raise HTTPException(status_code=400, detail=f"Invalid backend '{backend}'. Choose from 'jina', 'firecrawl', 'patchright', 'crawl4ai', 'scrapingant', 'scrapingbee', 'markdowner' or 'tavily.")

    if backend == "jina":
        result = await jina_reader_scrape(url)
        return result

    elif backend == "firecrawl":
        result = await firecrawl_scrape(url)
        return result

    elif backend == "crawl4ai":
        result = await crawl4ai_scrape(url)
        return result

    elif backend == "tavily":
        result = await tavily_scrape(url)
        return result

    elif backend == "scrapingant":
        result = await scrapingant_scrape(url)
        return result

    elif backend == "scrapingbee":
        result = await scrapingbee_scrape(url)
        return result

    elif backend == "markdowner":
        result = await markdowner_scrape(url)
        return result

    elif backend == "patchright":
        result = await patchright_scrape(url)
        return result

                
######## Deep-research endpoints
class DeepResearchRequest(BaseModel):
    topic: str = Field(..., description="The topic or question to research")
    maxDepth: int = Field(default=7, ge=1, le=10, description="Maximum depth of research iterations")
    timeLimit: int = Field(default=300, ge=30, le=600, description="Time limit in seconds")


# deep-research endpoint
@app.post("/v1/deep-research")
async def deep_research_endpoint(body: DeepResearchRequest):
    startTime = time.time()
    endpoint = get_endpoint(None, "FIRECRAWL_DEEP_RESEARCH_ENDPOINT", FIRECRAWL_DEEP_RESEARCH_ENDPOINT_DEFAULT)

    print(f"Deep searching {body.topic} with Firecrawl on {endpoint}")

    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    params = body.json(by_alias=True)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, headers=headers, data=params, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            endTime = time.time()
            log_request("deep-research", body.topic, "firecrawl", endpoint, 0, endTime-startTime)
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")




@app.get("/v1/deep-research/{id}")
async def deep_research_status_endpoint(id):
    endpoint = get_endpoint(None, "FIRECRAWL_DEEP_RESEARCH_ENDPOINT", FIRECRAWL_DEEP_RESEARCH_ENDPOINT_DEFAULT)

    print(f"Deep searching {id} status with Firecrawl on {endpoint}")

    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    endpoint = endpoint + f"/{id}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(endpoint, headers=headers, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


######## Extract endpoint
class ExtractRequest(BaseModel):
    urls: List[HttpUrl] = Field(...,description="A list of URLs to process. Maximum of 10 URLs allowed per request while in beta.",)
    prompt: Optional[str] = Field(None, description="An optional prompt to guide the processing of the URLs. Maximum length of 10,000 characters.",)
    schema: Optional[dict] = Field(None, description="An optional JSON schema to validate the structure of the data extracted from the URLs.",)
    ignoreSitemap: Optional[bool] = Field(False, description="If set to True, the sitemap of the URLs will be ignored during processing.",)
    includeSubdomains: Optional[bool] = Field(True, description="If set to True, subdomains of the provided URLs will be included in the processing.",)
    enableWebSearch: Optional[bool] = Field(False, description="If set to True, web search functionality will be enabled for the URLs.",)
    scrapeOptions: Optional[dict] = Field({"onlyMainContent": True}, description="Optional configuration for customizing the scraping behavior, such as focusing only on the main content.",)
    showSources: Optional[bool] = Field(False, description="If set to True, the sources of the extracted data will be included in the response.",)

# extract endpoint
@app.post("/v1/extract")
async def extract_endpoint(body: ExtractRequest):
    startTime = time.time()
    endpoint = get_endpoint(None, "FIRECRAWL_EXTRACT_ENDPOINT", FIRECRAWL_EXTRACT_ENDPOINT_DEFAULT)

    print(f"Extract {body.prompt} with Firecrawl on {endpoint}")

    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    params = body.json(by_alias=True)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, headers=headers, data=params, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            endTime = time.time()
            log_request("extract", body.prompt, "firecrawl", endpoint, 0, endTime-startTime)
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")



@app.get("/v1/extract/{id}")
async def extract_status_endpoint(id):
    endpoint = get_endpoint(None, "FIRECRAWL_EXTRACT_ENDPOINT", FIRECRAWL_EXTRACT_ENDPOINT_DEFAULT)

    print(f"Extract {id} status with Firecrawl on {endpoint}")

    api_key = get_api_key(None, "FIRECRAWL_API_KEY")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    endpoint = endpoint + f"/{id}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(endpoint, headers=headers, timeout=HTTP_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


######## Search endpoint


class ScrapeOptions(BaseModel):
    formats: list[Literal["markdown", "html", "rawHtml", "links", "screenshot", "screenshot@fullPage", "json"]] = None

class FirecrawlSearchModel(BaseModel):
    query: str
    limit: PositiveInt = SEARCH_RESULT_NUMBER_DEFAULT
    tbs: str | None = None
    lang: str = "en"
    country: str = "us"
    location: str | None = None
    timeout: NonNegativeInt = 60000
    scrapeOptions: ScrapeOptions | None = {}


#search combined endpoint
@app.post("/v1/search")
async def search_post(
    body: FirecrawlSearchModel,
    backend: Optional[str] = Query(None, description="Backend to use (optional)"),
    ):

    query = body.query
    limit = body.limit
    scrapeOptions = dict(body.scrapeOptions)
    
    if (scrapeOptions and scrapeOptions["formats"]):
        scrape = True
    else:
        scrape = False
    return await search(query, backend, limit, scrape)


#search combined endpoint
async def search(query: str, backend: str, limit: int, scrape: bool):
    if not backend:
        backend = SEARCH_BACKEND

    options = backend.split(',')
    if SEARCH_BACKEND_ROTATE == "random":
        # Split the string by comma to get a list of options
        # Randomly select one of the options
        backend = random.choice(options)
    #elif SEARCH_BACKEND_ROTATE == "sequential":
    else:
        global last_search_backend 
        if last_search_backend != None:
            last_search_backend = (last_search_backend + 1) % len(options)
            backend = options[last_search_backend]

        else:
            last_search_backend = 0
            backend = options[last_search_backend]

    if backend not in ["google", "searxng", "brave", "firecrawl", "serpapi", "tavily"]:
        raise HTTPException(status_code=400, detail=f"Invalid backend '{backend}'. Choose from 'google', 'searxng', 'brave', 'firecrawl', 'serpapi' or 'tavily'.")

    if backend == "google":
        result = await google_cse_search(query, limit=limit, scrape=scrape)
        return result

    elif backend == "searxng":
        result = await searxng_search(query, limit=limit, scrape=scrape)
        return result

    elif backend == "brave":
        result = await brave_search(query, limit=limit, scrape=scrape)
        return result

    elif backend == "firecrawl":
        result = await firecrawl_search(query, limit=limit, scrape=scrape)
        return result

    elif backend == "serpapi":
        result = await serpapi_search(query, limit=limit, scrape=scrape)
        return result

    elif backend == "tavily":
        result = await tavily_search(query, limit=limit, scrape=scrape)
        return result





######## Batch scrape

class BatchScrapeQuery(BaseModel):
    urls: list[HttpUrl]
                
@app.post("/v1/batch/scrape")
async def batch_scrape_post(
    body: BatchScrapeQuery,
    backend: Optional[str] = Query(None, description="Backend to use (optional)"), 
):
    urls = [str(http_url) for http_url in body.urls]
    
    return await batch_scrape(urls, backend)

# combined batch scrape endpoint
async def batch_scrape(urls: list[str], backend: str):
    if not backend:
        backend = SCRAPE_BACKEND
    
    if not backend:
        raise HTTPException(status_code=400, detail="Missing backend. Choose from 'firecrawl', 'crawl4ai' or 'tavily.")

    options = backend.split(',')
    if isinstance(options, list):
        try:
            options.remove("jina") # not compatible with batch scrape
        except:
            pass
        try:
            options.remove("markdowner") # not compatible with batch scrape
        except:
            pass
        if not options:
            raise HTTPException(status_code=400, detail="Missing backend. Choose from 'firecrawl', 'crawl4ai' or 'tavily.")
        if SCRAPE_BACKEND_ROTATE == "random":
            # Split the string by comma to get a list of options
            # Randomly select one of the options
            backend = random.choice(options)
        #elif SCRAPE_BACKEND_ROTATE == "sequential":
        else:
            global last_scrape_backend 
            if last_scrape_backend != None:
                last_scrape_backend = (last_scrape_backend + 1) % len(options)
                backend = options[last_scrape_backend]

            else:
                last_scrape_backend = 0
                backend = options[last_scrape_backend]

    if backend not in ["firecrawl", "crawl4ai", "tavily"]:
        raise HTTPException(status_code=400, detail=f"Invalid backend '{backend}'. Choose from 'firecrawl', 'crawl4ai' or 'tavily.")

    if backend == "firecrawl":
        result = await firecrawl_batch_scrape(urls)
        return result

    elif backend == "crawl4ai":
        result = await crawl4ai_batch_scrape(urls)
        return result

    elif backend == "tavily":
        result = await tavily_batch_scrape(urls)
        return result

