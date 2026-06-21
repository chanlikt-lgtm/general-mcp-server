from mcp.server.fastmcp import FastMCP
from tools.database import register_database_tools
from tools.files import register_file_tools
from tools.web import register_web_tools
from tools.prompts import register_prompts
from tools.text_math import register_text_math_tools
from tools.system import register_system_tools
from tools.data import register_data_tools
from tools.datetime_tools import register_datetime_tools
from tools.network import register_network_tools
from tools.image import register_image_tools
from tools.pdf_office import register_pdf_office_tools
from tools.crypto_security import register_crypto_security_tools
from tools.code_dev import register_code_dev_tools
from tools.audio_video import register_audio_video_tools
from tools.ml_utils import register_ml_utils_tools
from tools.web_scraping import register_web_scraping_tools
from tools.archive import register_archive_tools
from resources.data import register_resources

mcp = FastMCP(
    name="general-mcp-server",
    instructions="General-purpose MCP server: database, files, web tools"
)

register_database_tools(mcp)
register_file_tools(mcp)
register_web_tools(mcp)
register_resources(mcp)
register_prompts(mcp)
register_text_math_tools(mcp)
register_system_tools(mcp)
register_data_tools(mcp)
register_datetime_tools(mcp)
register_network_tools(mcp)
register_image_tools(mcp)
register_pdf_office_tools(mcp)
register_crypto_security_tools(mcp)
register_code_dev_tools(mcp)
register_audio_video_tools(mcp)
register_ml_utils_tools(mcp)
register_web_scraping_tools(mcp)
register_archive_tools(mcp)

if __name__ == "__main__":
    # stdio for local (Claude Desktop, Cursor)
    # switch to: mcp.run(transport="streamable-http", host="0.0.0.0", port=8080) for production
    mcp.run()
