from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient
import os

# Nạp URL MCP Toolbox của Cloud Run từ biến môi trường
toolbox_url = os.environ.get("MCP_TOOLBOX_URL", "https://mcp-toolbox-364283911624.asia-southeast1.run.app")

print(f"Đang kết nối tới MCP Toolbox tại: {toolbox_url}...")
toolbox = ToolboxSyncClient(toolbox_url)
tools = toolbox.load_toolset('default')

# Phân chia các công cụ cho từng Agent chuyên biệt
search_tool_names = ["find-hotels-by-price", "find-hotels-near-attraction"]
detail_tool_names = ["get-hotel-details", "get-hotel-facilities", "get-hotel-reviews"]

search_tools = [t for t in tools if t.__name__ in search_tool_names]
detail_tools = [t for t in tools if t.__name__ in detail_tool_names]

# 1. Agent chuyên trách Tìm kiếm Khách sạn
hotel_search_agent = Agent(
    name="hotel_search_agent",
    model="gemini-2.5-flash",
    description="Chuyên phụ trách tìm kiếm và lọc danh sách khách sạn tại Đà Nẵng dựa trên giá phòng hoặc vị trí địa lý.",
    instruction=(
        "Bạn là một trợ lý chuyên gia tìm kiếm khách sạn tại Đà Nẵng. Hãy sử dụng các công cụ được cung cấp để:\n"
        "- Tìm khách sạn có giá phòng dưới mức giá yêu cầu của người dùng.\n"
        "- Tìm khách sạn gần một địa danh hoặc điểm tham quan cụ thể (ví dụ: Cầu Rồng, bãi biển Mỹ Khê).\n"
        "Sau khi có kết quả, hãy liệt kê tên các khách sạn, loại phòng và giá cả một cách rõ ràng để người dùng lựa chọn."
    ),
    tools=search_tools
)

# 2. Agent chuyên trách Cung cấp Thông tin Chi tiết & Tiện ích Khách sạn
hotel_details_agent = Agent(
    name="hotel_details_agent",
    model="gemini-2.5-flash",
    description="Chuyên phụ trách cung cấp thông tin chi tiết, tiện ích (facilities), đặc điểm nổi bật và điểm số đánh giá (reviews) của một khách sạn cụ thể.",
    instruction=(
        "Bạn là một trợ lý chuyên gia về thông tin chi tiết khách sạn Đà Nẵng. Hãy sử dụng các công cụ được cung cấp để:\n"
        "- Lấy thông tin mô tả chi tiết, xếp hạng sao và thời gian check-in/out của khách sạn (`get-hotel-details`).\n"
        "- Lấy danh sách đầy đủ tất cả các tiện ích dịch vụ có sẵn của khách sạn (`get-hotel-facilities`).\n"
        "- Lấy điểm số đánh giá chi tiết của khách hàng (`get-hotel-reviews`).\n\n"
        "Nhiệm vụ quan trọng:\n"
        "1. Luôn sử dụng đúng công cụ truy vấn thông tin dựa trên tên khách sạn mà khách hàng hỏi.\n"
        "2. Tổng hợp tất cả các tiện ích nổi bật và điểm số đánh giá cao để làm nổi bật các đặc điểm ưu việt của khách sạn.\n"
        "3. Sử dụng khả năng của LLM để diễn đạt câu trả lời một cách tự nhiên, sinh động, lịch sự và thu hút khách hàng."
    ),
    tools=detail_tools
)

# 3. Agent Router chính (Điều phối câu hỏi)
root_agent = Agent(
    name="danang_hotel_agent",
    model="gemini-2.5-flash",
    description="Trợ lý du lịch Đà Nẵng chính, tiếp nhận yêu cầu và chuyển tiếp cuộc trò chuyện đến đúng Agent chuyên trách.",
    instruction=(
        "Bạn là trợ lý du lịch chính tại Đà Nẵng. Nhiệm vụ của bạn là phân tích ý định của người dùng và chuyển giao (transfer) cuộc trò chuyện:\n"
        "- Chuyển cuộc hội thoại cho `hotel_search_agent` nếu người dùng muốn tìm kiếm, lọc danh sách khách sạn theo giá phòng hoặc theo khoảng cách tới địa danh.\n"
        "- Chuyển cuộc hội thoại cho `hotel_details_agent` nếu người dùng hỏi về tiện ích (facilities), đặc điểm nổi bật, mô tả chi tiết hoặc điểm số đánh giá của một khách sạn cụ thể.\n"
        "Hãy luôn chào đón khách hàng thân thiện và điều phối chính xác."
    ),
    sub_agents=[hotel_search_agent, hotel_details_agent]
)
