"""Web scraping tools — BeautifulSoup + feedparser + urllib (no Selenium/Playwright).
   Works fully without a browser; JS-heavy sites may return incomplete results.
"""
import html
import re
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 15
_MAX_BYTES = 500_000   # 500 KB cap to prevent huge pages


def _fetch(url: str) -> tuple[str, str]:
    """Returns (html_text, error_str). On success error_str is ''."""
    if not url.startswith(("http://", "https://")):
        return "", "Error: URL must start with http:// or https://"
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read(_MAX_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace"), ""
    except urllib.error.HTTPError as e:
        return "", f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return "", f"URL error: {e.reason}"
    except Exception as e:
        return "", f"Error: {e}"


def register_web_scraping_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def scrape_page(url: str, selector: str = "") -> str:
        """
        Scrape the visible text content of a web page.
        url: full URL including https://, e.g. 'https://example.com'.
        selector: optional CSS selector to extract a specific element,
                  e.g. 'h1', 'article', '.main-content', '#product-description'.
                  If omitted, returns all visible body text (scripts/styles stripped).
        Returns up to 4000 characters of extracted text.
        Note: works on static HTML pages; JS-rendered content may be incomplete.
        """
        raw, err = _fetch(url)
        if err: return err
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw, "html.parser")
            # strip scripts/styles/nav/footer
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            if selector:
                el = soup.select(selector)
                if not el:
                    return f"No elements matched selector '{selector}'."
                text = "\n".join(e.get_text(separator=" ", strip=True) for e in el)
            else:
                text = soup.get_text(separator="\n", strip=True)
            # collapse whitespace
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            truncated = len(text) > 4000
            return text[:4000] + ("\n\n[...truncated]" if truncated else "")
        except Exception as e:
            return f"Error parsing HTML: {e}"

    @mcp.tool()
    def extract_links(url: str, same_domain_only: bool = False) -> str:
        """
        Extract all hyperlinks from a web page.
        url: full URL to scrape, e.g. 'https://example.com'.
        same_domain_only: if true, return only links on the same domain (default false).
        Returns up to 50 links with their anchor text and href.
        """
        raw, err = _fetch(url)
        if err: return err
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin, urlparse
            soup   = BeautifulSoup(raw, "html.parser")
            domain = urlparse(url).netloc
            links  = []
            seen   = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue
                full  = urljoin(url, href)
                if same_domain_only and urlparse(full).netloc != domain:
                    continue
                if full in seen:
                    continue
                seen.add(full)
                text = a.get_text(strip=True)[:80] or "(no text)"
                links.append(f"{text}\n  → {full}")
                if len(links) >= 50:
                    break
            return (
                f"Found {len(links)} links on {url}{'(same domain)' if same_domain_only else ''}:\n\n"
                + "\n\n".join(links)
            ) if links else "No links found."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def extract_tables(url: str) -> str:
        """
        Extract all HTML tables from a web page as formatted text.
        url: full URL to scrape, e.g. 'https://en.wikipedia.org/wiki/Python_(programming_language)'.
        Returns each table numbered with its rows and columns.
        Up to 5 tables and 20 rows per table are returned.
        """
        raw, err = _fetch(url)
        if err: return err
        try:
            from bs4 import BeautifulSoup
            soup   = BeautifulSoup(raw, "html.parser")
            tables = soup.find_all("table")
            if not tables:
                return "No tables found on the page."
            output = [f"Found {len(tables)} table(s) on {url}:\n"]
            for t_idx, table in enumerate(tables[:5], 1):
                rows = table.find_all("tr")
                output.append(f"\n=== Table {t_idx} ({len(rows)} rows) ===")
                for r_idx, row in enumerate(rows[:20]):
                    cells = row.find_all(["th", "td"])
                    line  = " | ".join(c.get_text(strip=True)[:30] for c in cells)
                    output.append(line)
                if len(rows) > 20:
                    output.append(f"  ... ({len(rows)-20} more rows)")
            return "\n".join(output)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def parse_rss(url: str, max_items: int = 10) -> str:
        """
        Parse an RSS or Atom feed and return the latest articles.
        url: RSS/Atom feed URL, e.g. 'https://feeds.bbci.co.uk/news/rss.xml'.
        max_items: max number of articles to return (default 10, max 30).
        Returns title, link, date, and summary for each item.
        """
        max_items = max(1, min(30, int(max_items)))
        try:
            import feedparser
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                return f"Error parsing feed: {feed.bozo_exception}"
            title   = feed.feed.get("title", "Unknown feed")
            entries = feed.entries[:max_items]
            if not entries:
                return f"Feed '{title}' has no entries."
            lines = [f"Feed: {title} ({len(feed.entries)} total items)\n"]
            for i, e in enumerate(entries, 1):
                pub = e.get("published", e.get("updated", "no date"))
                summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:200]
                lines.append(
                    f"{i}. {e.get('title','(no title)')}\n"
                    f"   URL : {e.get('link','')}\n"
                    f"   Date: {pub}\n"
                    f"   {summary.strip()}"
                )
            return "\n\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def get_page_metadata(url: str) -> str:
        """
        Extract SEO/Open Graph metadata from a web page.
        url: full URL, e.g. 'https://example.com'.
        Returns: title, description, keywords, og:title, og:image, canonical URL,
                 H1-H3 headings, and word count.
        """
        raw, err = _fetch(url)
        if err: return err
        try:
            from bs4 import BeautifulSoup
            soup  = BeautifulSoup(raw, "html.parser")

            def meta(name=None, prop=None):
                if name:
                    t = soup.find("meta", attrs={"name": name})
                else:
                    t = soup.find("meta", attrs={"property": prop})
                return t["content"].strip() if t and t.get("content") else "N/A"

            title     = soup.title.string.strip() if soup.title else "N/A"
            canonical = soup.find("link", rel="canonical")
            can_url   = canonical["href"] if canonical and canonical.get("href") else "N/A"
            h1s = [h.get_text(strip=True) for h in soup.find_all("h1")][:3]
            h2s = [h.get_text(strip=True) for h in soup.find_all("h2")][:5]
            for tag in soup(["script","style"]):
                tag.decompose()
            words = len(soup.get_text().split())

            return (
                f"Title       : {title}\n"
                f"Description : {meta(name='description')}\n"
                f"Keywords    : {meta(name='keywords')}\n"
                f"OG Title    : {meta(prop='og:title')}\n"
                f"OG Desc     : {meta(prop='og:description')}\n"
                f"OG Image    : {meta(prop='og:image')}\n"
                f"Canonical   : {can_url}\n"
                f"Word count  : ~{words}\n"
                f"H1 tags     : {h1s}\n"
                f"H2 tags     : {h2s}"
            )
        except Exception as e:
            return f"Error: {e}"
