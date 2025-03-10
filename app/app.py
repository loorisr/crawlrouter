from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, NonNegativeInt, PositiveInt, HttpUrl, root_validator, Field
from typing import Union, List, Optional, Literal
from markdownify import markdownify as md
import os
import time
import json
import sys
import httpx
import asyncio
import ast
import random
import yaml
import csv
from datetime import datetime
from jinja2 import Template, Environment, BaseLoader
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

#FIRECRAWL_SEARCH_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/search"
#FIRECRAWL_SCRAPE_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_BATCH_SCRAPE_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/batch/scrape"
FIRECRAWL_DEEP_RESEARCH_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/deep-research"
FIRECRAWL_DEEP_RESEARCH_ENDPOINT = os.getenv("FIRECRAWL_DEEP_RESEARCH_ENDPOINT")
FIRECRAWL_EXTRACT_ENDPOINT_DEFAULT = "https://api.firecrawl.dev/v1/extract"
#JINA_ENDPOINT_DEFAULT = "https://r.jina.ai/"

#CRAWL4AI_TIMEOUT = (int)(os.getenv("CRAWL4AI_TIMEOUT", 30))
HTTP_TIMEOUT = (int)(os.getenv("HTTP_TIMEOUT", 30))

SEARCH_BACKEND = os.getenv("SEARCH_BACKEND")
SCRAPE_BACKEND = os.getenv("SCRAPE_BACKEND")

SEARCH_BACKEND_ROTATE = os.getenv("SEARCH_BACKEND_ROTATE")
SCRAPE_BACKEND_ROTATE = os.getenv("SCRAPE_BACKEND_ROTATE")

SEARCH_RESULT_NUMBER_DEFAULT = 5

LOG_FILE = os.getenv("LOG_FILE")

last_search_backend = None # to rotate search engine
last_scrape_backend = None # to rotate scrape engine

app = FastAPI(    title="CrawlRouter",
   # description=description,
    summary="Unified API for Searching and Scraping",
    version="0.3.0",
    contact={
        "name": "loorisr",
        "url": "https://github.com/loorisr/crawlrouter"
    },
    license_info={
        "name": "GNU Affero General Public License v3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.en.html",
    },)

templates = Jinja2Templates(directory="templates")


# Initialize Jinja2 Environment
env = Environment(
   loader=BaseLoader(), # Or set the path where your config are
   # trim_blocks=True, # remove trailing spaces, tabs, and newlines from the start and end of a template block
   # lstrip_blocks=True, # Remove leading spaces and tabs from the start of a template block
)


def generic_resolver(data: dict, path: str):
    """Resolve dot-notated paths in nested data"""
    keys = path.split('.')
    for key in keys:
        if isinstance(data, list) and key.isdigit():
            data = data[int(key)] if int(key) < len(data) else None
        else:
            data = data.get(key, None) if isinstance(data, dict) else None
        if data is None:
            return None
    return data

def delete_empty_keys(data):
    def is_empty(value):
        if value is None:
            return True
        elif isinstance(value, str):
            return value == ""
        elif isinstance(value, (list, dict)):
            return len(value) == 0
        else:
            return False

    if isinstance(data, dict):
        for key in list(data.keys()):  # Use list to avoid runtime error due to changing size
            processed_value = delete_empty_keys(data[key])
            if is_empty(processed_value):
                del data[key]
            else:
                data[key] = processed_value
        return data if data else None
    elif isinstance(data, list):
        processed_list = []
        for item in data:
            processed_item = delete_empty_keys(item)
            if not is_empty(processed_item):
                processed_list.append(processed_item)
        return processed_list
    else:
        return data
    
async def render_config(response_config: dict, response: dict):
    """Recursively process configuration nodes"""
    if isinstance(response_config, dict):
        # Handle special directives
        if '_type' in response_config:
            if response_config['_type'] == 'array':
                source_data = generic_resolver(response, response_config.get('_path', '')) or []
                return [
                    await render_config(response_config['fields'], {'item': item})
                        for item in source_data
                ]
            
            if response_config['_type'] == 'object': # does not work
                source_data = generic_resolver(response, response_config.get('_path', '')) or {}
                return await render_config(
                    response_config['fields'], source_data)

        return {
            key: await render_config(value, response)
            for key, value in response_config.items()
            if not key.startswith('_')  # Skip internal directives
        }
    
    elif isinstance(response_config, list):
        return [await render_config(item, response) 
                for item in response_config]
    
    elif isinstance(response_config, str):
        # Render Jinja2 templates
        try:
            rendered = env.from_string(response_config).render(**response)
            # Try parsing as Python literal (e.g., int, dict, list)
            if isinstance(rendered, str):
                try:
                    rendered = ast.literal_eval(rendered)
                except (SyntaxError, ValueError):
                    pass
            # if rendered == None:
            #     rendered = ''
            return rendered
        except Exception as e:
            return f"Template Error: {str(e)}"
    
    return response_config

    
async def make_api_call(config: dict):
        method = config.get('method', 'GET').upper()
        url = config.get('url')
        if not url:
            raise ValueError("Missing URL in configuration")

        request_args = {
         #   'method': config.get('method', 'GET').upper(),
          #  'url': config.get('url'),
            'params': config.get('parameters', {}),
            'headers': config.get('headers', {}),
            'timeout': int(config.get('timeout', 10000))/1000,
        }

        if method == 'POST':
            request_args['json'] = config.get('data', {})

        delete_empty_keys(request_args)
        #print(method)
        #print(url)
        #print(request_args)
      
        async with httpx.AsyncClient() as client:
            try:
                #request = httpx.Request(**request_args)
                #response = await client.send(request)
                if method == "POST":
                    response = await client.post(url, **request_args)
                else:
                    response = await client.get(url, **request_args)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                try:
                    return response.json()
                except:
                    return {'text': response.text}
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail=str(e))
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
        

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
    location: dict = None # {"country": "US", "languages":"en-US"}
    removeBase64Images: bool = False
    blockAds: bool = True
    proxy: Literal["basic", "stealth"] = None


# Handle Firecrawl compatible endpoint
@app.post("/v1/scrape")
async def scrape_post(
    body: FirecrawlScapeModel,
    backend: Optional[str] = Query(None, description="Backend to use (optional)"),
    ):

    if not backend:
        backend = SCRAPE_BACKEND

    if not backend:
        backend = "jina"  # jina can be used without an API key

    options = backend.split(',')
    if SCRAPE_BACKEND_ROTATE == "random": # Randomly select one of the options
        # Split the string by comma to get a list of options
        backend = random.choice(options)
    else: # SCRAPE_BACKEND_ROTATE == "sequential":
        global last_scrape_backend 
        if last_scrape_backend != None:
            last_scrape_backend = (last_scrape_backend + 1) % len(options)
            backend = options[last_scrape_backend]
        else:
            last_scrape_backend = 0
            backend = options[last_scrape_backend]

    if backend not in ["jina", "firecrawl", "crawl4ai", "tavily", "scrapingant", "scrapingbee", "markdowner", "patchright"]:
        raise HTTPException(status_code=400, detail=f"Invalid backend '{backend}'. Choose from 'jina', 'firecrawl', 'patchright', 'crawl4ai', 'scrapingant', 'scrapingbee', 'markdowner' or 'tavily.")

    result = await scrape_handler(body, backend)
    
    return result


class PlaywrightServiceModel(BaseModel):
    url: HttpUrl = None
    wait_after_load: Optional[NonNegativeInt] = 0
    timeout: Optional[NonNegativeInt] = 15000
    headers: Optional[dict] = {}

# Handle playwright-service compatible endpoint
@app.post("/scrape")
async def scrape_page_endpoint(body: PlaywrightServiceModel):
    url = str(body.url)

    request = FirecrawlScapeModel(url=url, formats=["markdown"], headers=body.headers, timeout=body.timeout)
    scrapped_result = await scrape_post(request, None)

    result = {}
    result['content'] = scrapped_result['data']['markdown'] # should be rawHtml, needs to update scrape_single to take more parameters
    result['pageStatusCode'] = 200  # hack
    #result['pageStatusCode'] = scrapped_result['data']['metadata']['statusCode'] 
    
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
    #schema: Optional[dict] = Field(None, description="An optional JSON schema to validate the structure of the data extracted from the URLs.",)
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
    scrapeOptions: ScrapeOptions | None = None
 

# load backends config
with open("search_backends.yml") as f:
    search_backends = yaml.safe_load(f)

with open("scrape_backends.yml") as f:
    scrape_backends = yaml.safe_load(f)

with open("batch_scrape_backends.yml") as f:
    batch_scrape_backends = yaml.safe_load(f)


##############  handler scrape requests
async def scrape_handler(request: FirecrawlScapeModel, backend: str):
    print(f"Scraping {request.url} with {backend}")
    
    startTime = time.time()

    # Merge environment variables with request variables    
    context = {**os.environ, **(request.model_dump())}
        
    backend_config = scrape_backends.get(backend, {})

    request_config = backend_config.get('request', {})
    response_config = backend_config.get('response', {})

    request_config = await render_config(
        request_config,
        context,
    )
    

    # Make API call
    response =  await make_api_call(request_config)
            
    endTime = time.time()
    
    context = {**os.environ, **(response), 'processingTime': round(endTime-startTime, 3)}
    # Process response
    processed_response = await render_config(
        response_config,
        context,
    )

    log_request("scrape", str(request.url), backend, request_config['url'], 0, round(endTime-startTime, 3))
    return processed_response
        
##############  handler scrape requests



##############  handler search requests
async def search_handler(request: FirecrawlSearchModel, backend: str):
    print(f"Searching {request.query} with {backend}")

    startTime = time.time()

    # Merge environment variables with request variables    
    context = {**os.environ, **(request.model_dump())}
        
    backend_config = search_backends.get(backend, {})

    request_config = backend_config.get('request', {})
    response_config = backend_config.get('response', {})

    request_config = await render_config(
        request_config,
        context,
    )
    
    # Make API call
    response =  await make_api_call(request_config)
            
    endTime = time.time()
    #context = {**os.environ, **(response), **({'processingTime': round(endTime-startTime, 3)})}
    context = {**os.environ, **(response), 'processingTime': round(endTime-startTime, 3)}
    # Process response
    processed_response = await render_config(
        response_config,
        context,
    )

    processed_response['data'] = processed_response['data'][:request.limit] # some search engine, like searxng don't handle limit

    if request.scrapeOptions and request.scrapeOptions.formats: # user want to scrape all the results
        config = backend_config.get('config', {})
        # print(config)
        # print(config['scrape'])
        # print(config['scrape'].lower() in ['true', '1', 'y', 'yes'])
        if config and 'scrape' in config and (config['scrape'].lower() in ['false', '0', 'n', 'yes']): # the backend does not handle the scrape
            #print('do the scrape')
            #print(request.scrapeOptions.formats)
            all_urls = [item['url'] for item in processed_response['data']]
            #print(all_urls)
            batch_scrape_request = BatchScrapeQuery(urls=all_urls, formats=request.scrapeOptions.formats)
            scrapped_page = await batch_scrape_post(batch_scrape_request, backend=None)
            processed_response['data'] = combined_search_scrape(processed_response, scrapped_page['data'])

    return processed_response
        
##############  handler search requests


#search combined endpoint
@app.post("/v1/search")
async def search_post(
    body: FirecrawlSearchModel,
    backend: Optional[str] = Query(None, description="Backend to use (optional)"),
    ):

    # scrapeOptions = dict(body.scrapeOptions)
    
    # if (scrapeOptions and scrapeOptions["formats"]):
    #     scrape = True
    # else:
    #     scrape = False

    if not backend:
        backend = SEARCH_BACKEND

    options = backend.split(',')
    if SEARCH_BACKEND_ROTATE == "random": # Randomly select one of the options
        # Split the string by comma to get a list of options
        backend = random.choice(options)
    else: # we assume that SEARCH_BACKEND_ROTATE == "sequential":
        global last_search_backend 
        if last_search_backend != None:
            last_search_backend = (last_search_backend + 1) % len(options)
            backend = options[last_search_backend]
        else:
            last_search_backend = 0
            backend = options[last_search_backend]

    if backend not in ["google", "searxng", "brave", "firecrawl", "serpapi", "tavily", "serping"]:
        raise HTTPException(status_code=400, detail=f"Invalid backend '{backend}'. Choose from 'google', 'searxng', 'serping', 'brave', 'firecrawl', 'serpapi' or 'tavily'.")

    return await search_handler(body, backend)    


######## Batch scrape

class BatchScrapeQuery(BaseModel):
    urls: list[HttpUrl]
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
    location: dict = None # {"country": "US", "languages":"en-US"}
    removeBase64Images: bool = False
    blockAds: bool = True
    proxy: Literal["basic", "stealth"] = None



##############  handler batch scrape requests
async def batch_scrape_handler(request: BatchScrapeQuery, backend: str):
    urls = [str(http_url) for http_url in request.urls]
    print(f"Scraping {urls} with {backend}")
   
    startTime = time.time()
 
    request = request.model_dump() 
    request['urls'] = urls # hack to convert HttpUrl to str
    
    # Merge environment variables with request variables  
    context = {**os.environ, **request}
        
    backend_config = batch_scrape_backends.get(backend, {})

    request_config = backend_config.get('request', {})
    response_config = backend_config.get('response', {})
    poll_config = request_config.get('_poll', {})

    request_config = await render_config(
        request_config,
        context,
    )
    
    # Make API call
    response =  await make_api_call(request_config)
    
    #print(poll_config)

    if poll_config:
        #print("we need to pull the result")
        #print(response)
        result_url = response[poll_config['url']]
        #result_url = result_url.replace('https','http') # hack for local
        #print(f"polling {result_url}")


        timeout = int(poll_config['timeout'])
        start_poll = time.time()
        while True:
            if time.time() - start_poll > timeout:
                raise HTTPException(status_code=400, detail="Timeout exceeded")

            result = await make_request(result_url, headers=request_config['headers'], method="GET")

            if result["status"] == "completed":
                response = result
                break
                
            time.sleep(int(poll_config['interval']))
    
            
    endTime = time.time()
    
    context = {**os.environ, **(response), 'processingTime': round(endTime-startTime, 3)}
    # Process response
    processed_response = await render_config(
        response_config,
        context,
    )

    #print(f"scrape done")
    log_request("scrape", urls, backend, request_config['url'], 0, round(endTime-startTime, 3))
    return processed_response
        
##############  handler batch scrape requests

                
@app.post("/v1/batch/scrape")
async def batch_scrape_post(
    request: BatchScrapeQuery,
    backend: Optional[str] = Query(None, description="Backend to use (optional)"), 
):
    
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

    result = await batch_scrape_handler(request, backend)
    return result



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)