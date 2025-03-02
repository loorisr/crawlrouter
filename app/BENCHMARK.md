# Benchmark

This is a simple benchmark of several scraping tools. Tests have been made on 20 urls, using free trial of online tools.

## Cloud providers

| Provider           | # OK | %    | average time |
|--------------------|:----:|:----:|:------------:|
| Markdowner         | 18   | 90%  | 3.0          |
| ScrapingAnt-nojs   | 17   | 85%  | 8.2          |
| ScrapingAnt-js     | 13   | 65%  | 48.5         |
| ScrapingBee-nojs   | 18   | 90%  | 1.8          |
| ScrapingBee-js     | 19   | 95%  | 6.2          |
| Jina               | 20   | 100% | 3.3          |
| Tavily-basic       | 20   | 100% | 0.9          |
| Tavily-advanced    | 20   | 100% | 2.8          |
| ScrapingRobot-nojs | 19   | 95%  | 4.8          |
| ScrapingRobot-js   | 15   | 75%  | 7.9          |
| ScrapeOps-nojs     | 20   | 100% | 6.0          |
| ScrapeOps-js       | 20   | 100% | 7.8          |
| Firecrawl          | 17   | 85%  | 6.1          |

*nojs means that Javascript rendering is disabled*
*js means that Javascript rendering is enabled*

## Self-hosted

| Provider                          | # OK | %    | average time | Comments      |
|-----------------------------------|:----:|:----:|:------------:||:------------:|
| Firecrawl                         | 18   | 90%  | 15.7 | Firecrawl with default [Playwright service](https://github.com/mendableai/firecrawl/tree/main/apps/playwright-service-ts)|
| Patchright                        | 19   | 95%  | 16.8 | [Patchright service](https://github.com/loorisr/patchright-scrape-api) |
| Playwright                        | 18   | 90%  | 14.9 | [Playwright service](https://github.com/mendableai/firecrawl/tree/main/apps/playwright-service-ts) |
| Playwright-hyperbrowser           | 20   | 100% | 4.0  | Playwright service connected to a remote browser hosted by [Hperbrowser](https://www.hyperbrowser.ai/) |
| Crawl4AI                          | 20   | 100% | 17.0 | default configuration |


## Per website

| Address                        | # OK | %    |
|--------------------------------|:----:|:----:|
| https://perdu.com              | 19   | 95%  |
| https://www.bloomberg.com      | 15   | 75%  |
| https://www.20minutes.fr/      | 19   | 95%  |
| https://finance.yahoo.com/     | 19   | 95%  |
| https://www.firecrawl.dev/     | 19   | 95%  |
| https://www.nytimes.com/       | 17   | 85%  |
| https://www.google.com/        | 13   | 65%  |
| https://www.booking.com/       | 16   | 80%  |
| https://www.twitch.tv/         | 20   | 100% |
| https://www.fandom.com/explore | 18   | 90%  |
| https://www.quora.com/         | 19   | 95%  |
| https://www.amazon.com/        | 18   | 90%  |
| https://www.spotify.com/       | 18   | 90%  |
| https://www.wikimedia.org/     | 20   | 100% |
| https://www.reddit.com/        | 17   | 85%  |
| https://weather.com            | 16   | 80%  |
| https://edition.cnn.com/       | 16   | 80%  |
| https://www.imdb.com/          | 17   | 85%  |
| https://linkedin.com           | 16   | 80%  |
| https://samsung.com            | 19   | 95%  |