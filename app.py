from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from typing import Union, List, Optional
import os
import time
import sys
import httpx
import asyncio


FIRECRAWL_SEARCH_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/search"
FIRECRAWL_SCRAPE_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_BATCH_SCRAPE_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/batch/scrape"
JINA_ENDPOINT_DEFAULT = "https://r.jina.ai/"

CRAWL4AI_TIMEOUT = (float)(os.getenv("CRAWL4AI_TIMEOUT")) or 30.
HTTP_TIMEOUT = (float)(os.getenv("HTTP_TIMEOUT")) or 30.

SEARCH_BACKEND = os.getenv("SEARCH_BACKEND")
SCRAPE_BACKEND = os.getenv("SCRAPE_BACKEND")

SEARCH_RESULT_NUMBER_DEFAULT = 5

app = FastAPI(    title="CrawlRouter",
   # description=description,
    summary="Unified API for Searching and Crawling",
    version="0.0.1",
    contact={
        "name": "loorisr",
        "url": "https://github.com/loorisr/crawlrouter"
    },
    license_info={
        "name": "GNU Affero General Public License v3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
    },)

@app.get("/")
async def redirect_docs():
    return RedirectResponse(url="/docs")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    raise HTTPException(status_code=404, detail=f"Not found")

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

# Searxng endpoint
@app.get("/search/searxng")
async def searxng_search(query: str, api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None), limit: Optional[int] = Query(None), scrape: Optional[bool] = Query(None)):
   # api_key = get_api_key(api_key, "SEARXNG_API_KEY")
    endpoint = get_endpoint(endpoint, "SEARXNG_ENDPOINT")
    if not endpoint:
        raise HTTPException(status_code=500, detail="Missing Searxng endpoint. Provide in query or set environment variable SEARXNG_ENDPOINT")
    endpoint = endpoint.rstrip('/')
    url = f"{endpoint}/search"
    params = {"q": query, "format": "json"}

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
    
    return result

# Firecrawl scrape endpoint
@app.get("/scrape/firecrawl")
async def firecrawl_scrape(url: str, api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "FIRECRAWL_API_KEY")
    endpoint = get_endpoint(endpoint, "FIRECRAWL_SCRAPE_ENDPOINT", FIRECRAWL_SCRAPE_ENDPOINT_DEFAULT)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    body = {"url": url}
    print(f"Scraping {url} with Firecrawl on {endpoint}")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['backend'] = "firecrawl"
    return result

@app.api_route("/test", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"])
async def test_webhook(request: Request):
    print("Method:", request.method)
    print("Headers:", request.headers)
    print("Query params:", request.query_params)
    try:
        body = await request.json()
        print("Body:", body)
    except Exception:
        print("Body: (Not JSON)")
    return {"status": "ok"}

# Firecrawl batch scrape endpoint
@app.get("/batch/scrape/firecrawl") ################""
async def firecrawl_batch_scrape(urls: list[str], api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "FIRECRAWL_API_KEY")
    endpoint = get_endpoint(endpoint, "FIRECRAWL_BATCH_SCRAPE_ENDPOINT", FIRECRAWL_BATCH_SCRAPE_ENDPOINT_DEFAULT)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    body = {"urls": urls}#, "webhook": "http://192.168.10.121:8000/test"}
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
            return result
             
         time.sleep(1)
    
    

# Tavily scrape endpoint
@app.get("/scrape/tavily")
async def tavily_scrape(url: str, api_key: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "TAVILY_API_KEY")
    endpoint = "https://api.tavily.com/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    body = {"urls": url}
    print(f"Scraping {url} with Tavily")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['backend'] = "tavily"
    result['data'] = {}
    result['data']['markdown'] = result['results'][0]['raw_content']
    result['data']['metadata'] = {}
    result['data']['metadata']['url'] = result['results'][0]['url'] 
    del result['results']
    return result



# Tavily batch scrape endpoint
@app.get("/batch/scrape/tavily")
async def tavily_batch_scrape(urls: list[str] = Query(), api_key: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "TAVILY_API_KEY")
    endpoint = "https://api.tavily.com/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    body = {"urls": urls}
    print(f"Scraping {urls} with Tavily")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    
    result['data'] = {}
    result['data']['markdown'] = result['results'][0]['raw_content']
    result['data']['metadata'] = {}
    result['data']['metadata']['url'] = result['results'][0]['url'] 
    
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

    return cleaned_result



# Crawl4ai endpoint
@app.get("/scrape/crawl4ai")
async def crawl4ai_scrape(url: str, api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "CRAWL4AI_API_KEY")
    params = {"urls": url}
    endpoint = get_endpoint(endpoint, "CRAWL4AI_ENDPOINT")
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
        return result
    # result = await make_request(query_url, headers=headers, params=params, method="POST")
    # task_id = result["task_id"]
    # print(f"task_id {task_id}")

    # # Get results
    # query_url = f"{endpoint}/task/{task_id}"
    # print(f"{query_url}")
    # time.sleep(0.5)
    # result = await make_request(query_url, headers=headers, params=None)

    # # Poll for result
    # timeout = CRAWL4AI_TIMEOUT
    # start_time = time.time()
    # while True:
    #     if time.time() - start_time > timeout:
    #         #raise TimeoutError(f"Task {task_id} timeout")
    #         raise HTTPException(status_code=400, detail="Timeout exceeded")

    #     result = await make_request(query_url, headers=headers, params=None)

    #     if result["status"] == "completed":
    #         result['backend'] = "crawl4ai"
    #         result['data'] = result['result']
    #         result['success'] = result['data']['success']
    #         result['data']['metadata']['statusCode'] = result['data']['status_code'] 
    #         del result['result']
    #         del result['status']
    #         del result['created_at']
    #         del result['data']['response_headers']
    #         del result['data']['markdown_v2']
    #         del result['data']['media']
    #         del result['data']['links']
    #         del result['data']['html']
    #         del result['data']['cleaned_html']
    #         del result['data']['fit_html']
    #         del result['data']['fit_markdown']
    #         del result['data']['success']
    #         del result['data']['status_code'] 
    #         return result

    #     time.sleep(1)
            


# Crawl4ai batch scrape endpoint
@app.get("/batch/scrape/crawl4ai")
async def crawl4ai_batch_scrape(urls: list[str] = Query(), api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "CRAWL4AI_API_KEY")
    params = {"urls": urls}
    endpoint = get_endpoint(endpoint, "CRAWL4AI_ENDPOINT")
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

    return cleaned_result


@app.get("/scrape")
@app.get("/v1/scrape")
async def scrape_get(url: str, backend: Optional[str] = Query(None), api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    if backend:
        if backend not in ["jina", "firecrawl", "crawl4ai", "tavily"]:
            raise HTTPException(status_code=400, detail="Invalid backend. Choose from 'jina', 'firecrawl', 'crawl4ai' or 'tavily.")
    else: # parameter backend not defined
        if SCRAPE_BACKEND:
            backend = SCRAPE_BACKEND
        else: # jina can be used without an API key
            backend = "jina"

    if backend == "jina":
        result = await jina_reader_scrape(url, api_key=api_key, endpoint=endpoint)
        return result

    elif backend == "firecrawl":
        result = await firecrawl_scrape(url, api_key=api_key, endpoint=endpoint)
        return result

    elif backend == "crawl4ai":
        result = await crawl4ai_scrape(url, api_key=api_key, endpoint=endpoint)
        return result

    elif backend == "tavily":
        result = await tavily_scrape(url, api_key=api_key)
        return result


class ScrapeQuery(BaseModel):
    url: str
    backend: str | None = None
    api_key: str | None = None
    endpoint: str | None = None

                
@app.post("/scrape")
@app.post("/v1/scrape")
async def scrape_post(body: ScrapeQuery):
    url = body.url
    backend = body.backend
    api_key = body.api_key
    endpoint = body.endpoint
    
    return await scrape_get(url, backend, api_key, endpoint)

# Google CSE endpoint
@app.get("/search/cse")
async def google_cse_search(query: str, google_cse_id: Optional[str] = Query(None), google_cse_key: Optional[str] = Query(None), limit: Optional[int] = Query(None), scrape: Optional[bool] = Query(None)):
    google_cse_id = get_api_key(google_cse_id, "GOOGLE_CSE_ID") 
    google_cse_key = get_api_key(google_cse_key, "GOOGLE_CSE_KEY")

    num = limit

    url = "https://customsearch.googleapis.com/customsearch/v1"
    params = {"q": query, "cx": google_cse_id, "key": google_cse_key, "num": num}
    print(f"Searching {query} with Google")
    result = await make_request(url, params=params)
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

    return result


# BRAVE Search API endpoint
@app.get("/search/brave")
async def brave_search(query: str, api_key: Optional[str] = Query(None)):
    api_key = get_api_key(api_key, "BRAVE_API_KEY")
    endpoint = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": api_key, "Accept-Encoding": "gzip", "Accept": "application/json"}
    params = {"q": query}
    print(f"Searching {query} with Brave")
    result = await make_request(endpoint, params=params, headers=headers)
    result['backend'] = "brave"
    return result



# Firecrawl Search endpoint
@app.get("/search/firecrawl")
async def firecrawl_search(query: str, api_key: Optional[str] = Query(None), limit: Optional[int] = Query(None), scrape: Optional[bool] = Query(None)):
    api_key = get_api_key(api_key, "FIRECRAWL_API_KEY")
    endpoint = get_endpoint(None, "FIRECRAWL_SEARCH_ENDPOINT", FIRECRAWL_SEARCH_ENDPOINT_DEFAULT)
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    number_of_results = limit

    body = {"query": query}
    if scrape:
        body["scrapeOptions"] = {}
        body["scrapeOptions"]["formats"] = ["markdown"]
        
    print(f"Searching {query} with Firecrawl on {endpoint}")
    result = await make_request(endpoint, params=body, headers=headers, method="POST")
    result['data'] = result['data'][:number_of_results]
    result['backend'] = "firecrawl"
    return result


# SerpAPI search endpoint
@app.get("/search/serpapi")
async def serpapi_search(query: str, api_key: Optional[str] = Query(None), limit: Optional[int] = Query(None), scrape: Optional[bool] = Query(None)):
    api_key = get_api_key(api_key, "SERPAPI_KEY")
    endpoint = "https://serpapi.com/search"
    
    num = limit

    params = {"q": query, "api_key": api_key, "num": num}
    print(f"Searching {query} with SerpAPI")
    result = await make_request(endpoint, params=params)
    result['backend'] = "serpapi"
    del result['search_metadata']
    del result['search_parameters']
    del result['search_information']
    del result['knowledge_graph']
    del result['related_questions']
    del result['related_searches']
    del result['answer_box']
    del result['top_stories']
    del result['top_stories_link']
    del result['top_stories_serpapi_link']
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


    if scrape:
        all_urls = [item['url'] for item in result['data']]
        scrapped_page = await batch_scrape_get(urls=all_urls, backend=None, api_key=None, endpoint=None)
        result['data'] = combined_search_scrape(result, scrapped_page['data'])

    return result

# Tavily search endpoint
@app.get("/search/tavily")
async def tavily_search(query: str, api_key: Optional[str] = Query(None), limit: Optional[int] = Query(None), scrape: Optional[bool] = Query(None)):
    api_key = get_api_key(api_key, "TAVILY_API_KEY")
    endpoint = "https://api.tavily.com/search"

    max_results = limit
    
    body = {"query": query, "max_results": max_results}
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
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
            scrapped_page = await scrape_get(url=res['url'], backend=None, api_key=None, endpoint=None)
            res['markdown'] = scrapped_page['data']['markdown']
    del result['results']
    del result['response_time']
    del result['images']
    del result['answer']
    del result['query']
    del result['follow_up_questions']
    return result

# Jina Reader endpoint
@app.get("/scrape/jina")
async def jina_reader_scrape(url: str, api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    api_key = api_key or os.environ.get("JINA_API_KEY") 
    endpoint = get_endpoint(endpoint, "JINA_ENDPOINT", JINA_ENDPOINT_DEFAULT)
    headers = {"Accept": "application/json"}
    if api_key:
        #api_key = get_api_key(jina_api_key, "JINA_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    url = f"{endpoint.rstrip('/')}/{url}"
    print(f"Scraping {url} with Jina on {endpoint}")
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
    return result



#search combined endpoint
@app.get("/search")
@app.get("/v0/search")
async def search_get(query: str, backend: Optional[str] = Query(None), endpoint: Optional[str] = Query(None), google_cse_id: Optional[str] = Query(None), google_cse_key: Optional[str] = Query(None), api_key: Optional[str] = Query(None), limit: Optional[int] = Query(None), scrape: Optional[bool] = Query(None)):
    if backend:
        if backend not in ["google", "searxng", "brave", "firecrawl", "serpapi", "tavily"]:
            raise HTTPException(status_code=400, detail="Invalid backend. Choose from 'google', 'searxng', 'brave', 'firecrawl', 'serpapi' or 'tavily'.")
    else:
        if google_cse_key and google_cse_id:
            backend = "google"
        elif SEARCH_BACKEND:
            backend = SEARCH_BACKEND
        else:
            raise HTTPException(status_code=400, detail="Search backend missing.")


    if not limit:
        limit = SEARCH_RESULT_NUMBER_DEFAULT

    if backend == "google":
        result = await google_cse_search(query, google_cse_id=google_cse_id, google_cse_key=google_cse_key, limit=limit, scrape=scrape)
        return result

    elif backend == "searxng":
        result = await searxng_search(query, api_key=api_key, endpoint=endpoint, limit=limit, scrape=scrape)
        return result

    elif backend == "brave":
        result = await brave_search(query, api_key=api_key, scrape=scrape)
        return result

    elif backend == "firecrawl":
        result = await firecrawl_search(query, api_key=api_key, limit=limit, scrape=scrape)
        return result

    elif backend == "serpapi":
        result = await serpapi_search(query, api_key=api_key, limit=limit, scrape=scrape)
        return result

    elif backend == "tavily":
        result = await tavily_search(query, api_key=api_key, limit=limit, scrape=scrape)
        return result



class SearchQuery(BaseModel):
    query: str
    backend: str | None = None
    api_key: str | None = None
    endpoint: str | None = None
    limit: Optional[int] = SEARCH_RESULT_NUMBER_DEFAULT
    google_cse_key: str | None = None
    google_cse_id: str | None = None
    scrapeOptions: dict = []
    scrape: bool | None = None


#search combined endpoint
@app.post("/search")
@app.post("/v0/search")
@app.post("/v1/search")
async def search_post(body: SearchQuery):
    backend = body.backend
    query = body.query
    endpoint = body.endpoint
    api_key = body.api_key
    google_cse_key = body.google_cse_key
    google_cse_id = body.google_cse_id
    limit = body.limit
    scrapeOptions = body.scrapeOptions
    scrape = body.scrape
    if scrape or (scrapeOptions and scrapeOptions["formats"] and scrapeOptions["formats"][0] == "markdown"):
        scrape = True
    else:
        scrape = False
    return await search_get(query, backend, endpoint, google_cse_id, google_cse_key, api_key, limit, scrape)






@app.get("/v1/batch/scrape")
async def batch_scrape_get(urls: list[str] = Query(), backend: Optional[str] = Query(None), api_key: Optional[str] = Query(None), endpoint: Optional[str] = Query(None)):
    if backend:
        if backend not in ["firecrawl", "crawl4ai", "tavily"]:
            raise HTTPException(status_code=400, detail="Invalid backend. Choose from 'firecrawl', 'crawl4ai' or 'tavily.")
    else: # parameter backend not defined
        if SCRAPE_BACKEND:
            backend = SCRAPE_BACKEND
        else: 
            raise HTTPException(status_code=400, detail="Missing backend. Choose from 'firecrawl', 'crawl4ai' or 'tavily.")

    if backend == "firecrawl":
        result = await firecrawl_batch_scrape(urls, api_key=api_key, endpoint=endpoint)
        return result

    elif backend == "crawl4ai":
        result = await crawl4ai_batch_scrape(urls, api_key=api_key, endpoint=endpoint)
        return result

    elif backend == "tavily":
        result = await tavily_batch_scrape(urls, api_key=api_key)
        return result


class BatchScrapeQuery(BaseModel):
    urls: list[str]
    backend: str | None = None
    api_key: str | None = None
    endpoint: str | None = None

                
@app.post("/v1/batch/scrape")
async def batch_scrape_post(body: BatchScrapeQuery):
    urls = body.urls
    backend = body.backend
    api_key = body.api_key
    endpoint = body.endpoint
    
    return await batch_scrape_get(urls, backend, api_key, endpoint)
