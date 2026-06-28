# Hướng dẫn Kỹ thuật & Thiết lập Hệ thống AI Travel Agent trên GCP (Console UI)

Tài liệu này cung cấp hướng dẫn kỹ thuật chi tiết nhất để thiết lập và vận hành hệ thống AI Travel Agent trên Google Cloud Platform (GCP). Thay vì sử dụng các câu lệnh gcloud/bq phức tạp, tài liệu này tập trung vào các thao tác thực hiện trực tiếp bằng giao diện Web đồ họa (GCP Console).

---

## 1. Sơ đồ Luồng Công việc (Workflow Diagram)

Dưới đây là sơ đồ chi tiết luồng xử lý dữ liệu và luồng vận hành của hệ thống Multi-Agent, bắt đầu từ nguồn dữ liệu thô đến khi trả lời người dùng:

```mermaid
graph TD
    subgraph "1. Nguồn Dữ liệu & Lưu trữ (Data Source)"
        CSV[raw_hotels_full.csv (Local File)] -->|gcloud storage cp| GCS[(Cloud Storage Bucket)]
        Scraper[Bộ cào dữ liệu tự động <br><i>(Chưa thực hiện - Dự kiến tích hợp trong tương lai)</i>] -->|Daily Trigger| GCS
    end

    subgraph "2. Tiến trình ETL Tự động (Serverless ETL Pipeline)"
        Scheduler[Cloud Scheduler <br>Daily Trigger 00:00] -->|HTTP POST Request| RunJob[Cloud Run Job: danang-etl-job]
        GCS -->|Download CSV| RunJob
        RunJob -->|Bước 1: preprocess.py| CleanData[Làm sạch & tách phòng]
        CleanData -->|Bước 2: load_to_cloud_sql.py| DB_Load[Nạp dữ liệu]
    end

    subgraph "3. Cơ sở dữ liệu & Báo cáo (Destination Databases & BI)"
        DB_Load -->|Nạp dữ liệu OLTP| CloudSQL[(Cloud SQL PostgreSQL)]
        DB_Load -->|Nạp dữ liệu OLAP| BigQuery[(BigQuery)]
        BigQuery -->|Kết nối dữ liệu BI| Looker[Looker Studio <br><i>(Báo cáo & Dashboard phân tích xu hướng)</i>]
    end

    subgraph "4. Tích hợp AI & Công cụ (AI & Agent Engine)"
        Secret[Secret Manager: mcp-tools-config] -->|Mount tools.yaml| MCP[Cloud Run: mcp-toolbox <br><i>(MCP Server)</i>]
        CloudSQL -->|Database queries| MCP
        
        AgentUI[Cloud Run: danang-agent-service <br><i>(Agent Web UI)</i>] <-->|Tool Execution Protocols| MCP
        AgentUI <-->|API Requests| Gemini[Vertex AI: Gemini 2.5 Flash]
    end

    subgraph "5. Tương tác Người dùng (User Interaction)"
        User[User Web Browser] <-->|Giao diện Chat| AgentUI
    end

    style Scraper fill:#ffccf2,stroke:#333,stroke-width:2px,stroke-dasharray: 5 5
    style Looker fill:#e8f0fe,stroke:#1a73e8,stroke-width:2px
```

---

## 2. Các Công cụ và Dịch vụ GCP Sử dụng

Hệ thống kết hợp các dịch vụ đám mây hàng đầu của Google để đảm bảo tính bảo mật, hiệu năng và khả năng tự động mở rộng (Serverless):

1. **Cloud Storage (GCS) - Hồ dữ liệu thô (Data Lake)**:
   - *Vai trò*: Lưu trữ tệp tin dữ liệu thô `raw_hotels_full.csv` (dung lượng khoảng 2.8 MB, chứa 542 dòng dữ liệu khách sạn kèm phòng và giá thô). Đây là nơi tách biệt dữ liệu tĩnh khỏi container để dễ dàng cập nhật mà không cần deploy lại code.
2. **Cloud SQL for PostgreSQL - Cơ sở dữ liệu Giao dịch (OLTP)**:
   - *Vai trò*: Lưu trữ các bảng dữ liệu quan hệ đã được chuẩn hóa phục vụ cho ứng dụng AI Agent truy vấn thời gian thực với độ trễ cực thấp (<100ms). Chứa 7 bảng dữ liệu quan hệ: `hotels`, `hotel_locations`, `hotel_facilities`, `hotel_nearby_places`, `hotel_reviews`, `room_types`, `room_prices`.
3. **BigQuery - Kho dữ liệu phân tích lịch sử (OLAP)**:
   - *Vai trò*: Lưu trữ lịch sử biến động giá phòng và phục vụ phân tích xu hướng lâu dài mà không làm ảnh hưởng đến hiệu năng của Cloud SQL đang chạy trực tiếp.
4. **Cloud Run Jobs - Xử lý Batch ETL Serverless**:
   - *Vai trò*: Khởi chạy một container tạm thời để thực hiện quy trình ETL (Làm sạch và nạp dữ liệu) và tự động tắt ngay sau khi hoàn thành để tiết kiệm chi phí tối đa.
5. **Cloud Run Services - Chạy dịch vụ API & Agent**:
   - *Vai trò*: Chạy dịch vụ MCP Toolbox và Agent Chat liên tục. Hỗ trợ cấu hình **Scale-to-Zero** (tự động giảm số lượng container hoạt động về 0 khi không có người dùng nhắn tin để giảm chi phí về 0 USD).
6. **Cloud Scheduler - Bộ kích hoạt ETL định kỳ**:
   - *Vai trò*: Lập lịch tự động chạy quy trình ETL vào lúc 00:00 hàng ngày (Giờ Việt Nam) bằng cách gửi một HTTP POST request bảo mật có kèm mã xác thực OIDC Service Account tới API của Cloud Run Job.
   - *Mở rộng trong tương lai*: Lập lịch kích hoạt thêm bộ cào dữ liệu tự động (Web Scraper) để cào dữ liệu mới nhất từ các trang web đặt phòng trước khi tiến hành tiền xử lý và nạp dữ liệu. (Cơ chế cào này hiện tại chưa thực hiện).
7. **Secret Manager**:
   - *Vai trò*: Lưu trữ bảo mật các tham số nhạy cảm (mật khẩu database, token kết nối). Tệp cấu hình công cụ `tools.yaml` chứa thông tin đăng nhập PostgreSQL sẽ được lưu trong Secret Manager và được mount trực tiếp thành một tệp `/app/tools.yaml` trong container lúc runtime.
8. **Vertex AI (Gemini 2.5 Flash)**:
   - *Vai trò*: Trí tuệ cốt lõi của Travel Agent. Nhận diện ý định ngôn ngữ tự nhiên của người dùng để quyết định chuyển giao hội thoại giữa các agent con hoặc chuyển đổi thành các lời gọi hàm (Function Calling) tương ứng với các công cụ trong MCP Toolbox.
9. **Artifact Registry**:
   - *Vai trò*: Kho lưu trữ tập trung các Docker Container Image được build từ mã nguồn thô thông qua Cloud Build.
10. **Looker Studio**:
    - *Vai trò*: Công cụ Báo cáo & Dashboard BI. Kết nối trực tiếp với BigQuery để trực quan hóa dữ liệu và lịch sử biến động giá thành các báo cáo đồ họa trực quan phục vụ phân tích xu hướng kinh doanh.

---

## 3. Vai trò của các File mã nguồn ETL & Database local

- **[etl/preprocess.py](file:///e:/Booking/etl/preprocess.py)**: Chứa logic tiền xử lý dữ liệu. Đọc file CSV thô, chuẩn hóa ký tự tiếng Việt, bóc tách địa chỉ, làm sạch số lượng sao, tính toán chuyển đổi khoảng cách địa danh về dạng mét, và tách cột danh sách phòng/giá thành các dòng độc lập.
- **[etl/load_to_cloud_sql.py](file:///e:/Booking/etl/load_to_cloud_sql.py)**: Chứa logic nạp dữ liệu. Đọc các file dữ liệu sạch đã được chuẩn hóa và thực hiện lệnh chèn theo lô (batch insert) vào 7 bảng cơ sở dữ liệu trên Cloud SQL theo đúng trình tự khóa ngoại.
- **[etl/run_etl.py](file:///e:/Booking/etl/run_etl.py)**: Tập lệnh điều phối chính của Cloud Run Job, thực thi tuần tự `preprocess.py` và `load_to_cloud_sql.py`.
- **[database/schema.sql](file:///e:/Booking/database/schema.sql)**: Định nghĩa cấu trúc 7 bảng cơ sở dữ liệu quan hệ và các chỉ mục (indexing) để tối ưu truy vấn SQL cho AI Agent.
- **[database/init_db.py](file:///e:/Booking/database/init_db.py)**: Đọc file `schema.sql` và kết nối trực tiếp đến PostgreSQL để khởi tạo cấu trúc bảng.
- **[database/check_db.py](file:///e:/Booking/database/check_db.py)**: Thực hiện câu lệnh đếm dòng trên các bảng để xác minh số lượng bản ghi đã được nạp thành công.

---

## 4. Hướng dẫn Từng bước Thiết lập trên Web GCP Console

### Bước 1: Kích hoạt các API dịch vụ thiết yếu
1. Mở trình duyệt và truy cập vào [Google Cloud Console](https://console.cloud.google.com/).
2. Chọn dự án của bạn (ví dụ: `capstone-project-2-group-4`) ở menu thả xuống phía trên cùng.
3. Nhấp vào biểu tượng Menu (3 dấu gạch ngang góc trên bên trái) -> chọn **APIs & Services** -> chọn **Library**.
4. Lần lượt tìm kiếm các API sau và nhấn nút **Enable** (Kích hoạt) cho từng dịch vụ:
   - `Cloud Storage API`
   - `Cloud SQL Admin API`
   - `Cloud Run Admin API`
   - `Cloud Build API`
   - `Secret Manager API`
   - `Vertex AI API`
   - `Cloud Scheduler API`
   - `BigQuery API`
   - `Artifact Registry API`

---

### Bước 2: Tạo Service Account và Gán quyền IAM

#### 1. Tạo Service Account
1. Mở Menu bên trái -> chọn **IAM & Admin** -> chọn **Service Accounts**.
2. Nhấp vào nút **+ CREATE SERVICE ACCOUNT** ở trên cùng.
3. Nhập các thông tin sau:
   - **Service account name**: `mcp-toolbox-sa`
   - **Description**: `SA for MCP Toolbox and Services`
4. Nhấn **CREATE AND CONTINUE** rồi nhấn **DONE** để hoàn thành tạo tài khoản.

#### 2. Gán quyền IAM cho Service Account
1. Đi tới tab **IAM** (ở menu bên trái, ngay trên Service Accounts).
2. Nhấp vào nút **GRANT ACCESS** ở đầu trang.
3. Ở ô **New principals**, nhập email của Service Account vừa tạo:  
   `mcp-toolbox-sa@capstone-project-2-group-4.iam.gserviceaccount.com`
4. Ở phần **Assign roles**, lần lượt tìm kiếm và thêm các vai trò sau bằng cách nhấn **+ ADD ANOTHER ROLE**:
   - **Cloud SQL Client** (`roles/cloudsql.client`)
   - **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`)
   - **Storage Object Admin** (`roles/storage.objectAdmin`)
   - **Cloud Run Developer** (`roles/run.developer`)
5. Nhấp vào nút **SAVE** để lưu lại cấu hình.

---

### Bước 3: Thiết lập Cloud Storage (GCS)

1. Mở Menu bên trái -> chọn **Cloud Storage** -> chọn **Buckets**.
2. Nhấp vào nút **+ CREATE** ở thanh công cụ phía trên.
3. Nhập tên bucket: `capstone-project-2-group-4-data` rồi nhấn **CONTINUE**.
4. Ở phần **Location type**, chọn **Region** và chọn vùng **asia-southeast1 (Singapore)**. Nhấn **CONTINUE**.
5. Giữ các cấu hình mặc định khác và nhấn nút **CREATE** ở cuối trang.
6. Khi bucket được tạo, bạn sẽ được tự động chuyển vào trang chi tiết của bucket. Nhấp vào nút **UPLOAD FILES**.
7. Chọn tệp [raw_hotels_full.csv](file:///e:/Booking/data/raw_hotels_full.csv) từ máy của bạn để tải lên.

---

### Bước 4: Khởi tạo PostgreSQL trên Cloud SQL

1. Mở Menu bên trái -> chọn **Databases** -> chọn **SQL**.
2. Nhấp vào nút **CREATE INSTANCE** ở trên cùng.
3. Chọn cơ sở dữ liệu **PostgreSQL**.
4. Điền các thông tin cấu hình thực thể:
   - **Instance ID**: `danang-hotels-db`
   - **Password**: Nhấp chọn hoặc điền mật khẩu mạnh: `Capstone2_2026`
   - **Database version**: Chọn **PostgreSQL 15**.
   - **Cloud SQL edition**: Chọn **Enterprise**.
   - **Preset**: Chọn **Sandbox** (phù hợp với môi trường thử nghiệm và cấu hình `db-f1-micro`).
   - **Region**: Chọn vùng **asia-southeast1 (Singapore)**.
5. Cuộn xuống phần **Configuration options** để tùy chỉnh hạ tầng:
   - Mở mục **Machine configuration**: Chọn loại máy **Shared core** -> chọn **db-f1-micro**.
   - Mở mục **Connections**:
     - Đảm bảo đã chọn **Public IP**.
     - Nhấp chọn **+ ADD NETWORK** để thêm mạng được phép kết nối từ local.
     - **Name**: `Local PC`
     - **Network**: Nhập IP public của máy bạn (ví dụ: `42.117.146.182/32`).
6. Nhấp vào nút **CREATE INSTANCE** ở cuối trang. *(Quá trình tạo database sẽ mất khoảng 5-10 phút).*

---

### Bước 5: Khởi tạo Tập dữ liệu BigQuery

1. Mở Menu bên trái -> chọn **Analytics** -> chọn **BigQuery**.
2. Trong bảng điều khiển **Explorer** bên trái, tìm tên dự án của bạn (`capstone-project-2-group-4`).
3. Nhấp vào biểu tượng **3 dấu chấm dọc** bên cạnh tên dự án -> chọn **Create dataset**.
4. Điền thông tin tạo Dataset:
   - **Dataset ID**: `danang_hotels_analytics`
   - **Data location**: Chọn **asia-southeast1 (Singapore)**.
5. Nhấp vào nút **CREATE DATASET**.

---

### Bước 6: Cấu hình Secret Manager

1. Mở Menu bên trái -> chọn **Security** -> chọn **Secret Manager**.
2. Nhấp vào nút **+ CREATE SECRET** ở trên cùng.
3. Điền các thông tin:
   - **Name**: `mcp-tools-config`
   - **Secret value**: Sao chép toàn bộ nội dung của tệp cấu hình [tools.yaml](file:///e:/Booking/mcp/tools.yaml) của bạn và dán vào khung văn bản.
4. Nhấp vào nút **CREATE SECRET**.

---

### Bước 7: Triển khai MCP Database Toolbox trên Cloud Run

1. Mở Menu bên trái -> chọn **Serverless** -> chọn **Cloud Run**.
2. Nhấp vào nút **+ CREATE SERVICE** ở trên cùng.
3. Chọn **Deploy one revision from an existing container image**.
4. Nhập đường dẫn image vào ô **Container image URL**:  
   `us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest`
5. Thiết lập thông tin Service:
   - **Service name**: `mcp-toolbox`
   - **Region**: Chọn vùng **asia-southeast1 (Singapore)**.
   - **CPU allocation and pricing**: Chọn **CPU is only allocated during request processing** (để cấu hình Scale-to-Zero).
   - **Autoscaling**: Thiết lập số lượng instance tối thiểu (**Minimum number of instances**) là `0` và tối đa là `10`.
   - **Ingress control**: Chọn **All** (để nhận yêu cầu từ internet).
   - **Authentication**: Chọn **Allow unauthenticated invocations**.
6. Cuộn xuống và mở rộng mục **Container, Connections, Security** ở cuối trang để cấu hình chi tiết:
   - Tab **CONTAINER**:
     - Cuộn xuống phần **Container arguments**: Nhấn **+ ADD ARGUMENT** để thêm lần lượt 3 đối số:
       1. `--config=/app/tools.yaml`
       2. `--address=0.0.0.0`
       3. `--port=8080`
   - Tab **SECURITY**:
     - Ở ô **Service account**, chọn tài khoản: `mcp-toolbox-sa@capstone-project-2-group-4.iam.gserviceaccount.com`
     - Cuộn xuống phần **Secrets**: Nhấp **+ REFER A SECRET**.
       - **Secret**: Chọn `mcp-tools-config`.
       - **Reference method**: Chọn **Mounted as volume**.
       - **Mount path**: Nhập `/app/tools.yaml`.
   - Tab **CONNECTIONS**:
     - Cuộn xuống mục **Cloud SQL connections** -> Nhấp **+ ADD CONNECTION**.
     - Chọn thực thể database bạn đã tạo: `danang-hotels-db`.
7. Nhấp vào nút **CREATE** ở cuối trang để tiến hành triển khai. Sau khi deploy thành công, hãy sao chép lại **Service URL** hiển thị ở trên cùng.

---

### Bước 8: Triển khai và Chạy Cloud Run Job (ETL Pipeline)

1. Mở Menu bên trái -> chọn **Serverless** -> chọn **Cloud Run**.
2. Chọn tab **JOBS** ở thanh menu ngang phía trên.
3. Nhấp vào nút **+ Deploy container** ở thanh công cụ phía trên (như hiển thị trên giao diện Cloud Run Jobs của bạn).
4. Điền thông tin **Container image URL**:
   Để Cloud Run Job hoạt động, nó bắt buộc cần một container image đã được biên dịch từ mã nguồn. Bạn có 2 cách để chọn:
   * **Cách A (Sử dụng Image đã build sẵn - Khuyên dùng)**:
     - Nhấp nút **SELECT** cạnh ô nhập hoặc dán trực tiếp đường dẫn container image đã được sinh ra từ quá trình build tự động trước đó:
       `asia-southeast1-docker.pkg.dev/capstone-project-2-group-4/cloud-run-source-deploy/danang-etl-job:latest`
   * **Cách B (Tự tạo quy trình build tự động từ Web Console)**:
     - Bạn truy cập vào **Cloud Build** -> tạo **Trigger** kết nối đến repository chứa mã nguồn (GitHub/Cloud Source Repositories) và cấu hình tự động build image mỗi khi có code mới để đẩy vào Artifact Registry. Sau đó chọn đường dẫn image đó tại đây.
5. Nhập các thông tin cấu hình:
   - **Job name**: `danang-etl-job`
   - **Region**: Chọn **asia-southeast1 (Singapore)**.
6. Mở rộng mục **Container, Connections, Security**:
   - Tab **SECURITY**:
     - Chọn **Service account**: `mcp-toolbox-sa@capstone-project-2-group-4.iam.gserviceaccount.com`
   - Tab **CONNECTIONS**:
     - Thêm kết nối Cloud SQL: Chọn `danang-hotels-db`.
   - Tab **VARIABLES & SECRETS**:
     - Thêm các biến môi trường sau:
       - `DB_HOST`: `/cloudsql/capstone-project-2-group-4:asia-southeast1:danang-hotels-db`
       - `DB_PORT`: `5432`
       - `DB_NAME`: `postgres`
       - `DB_USER`: `postgres`
       - `DB_PASSWORD`: `Capstone2_2026`
7. Nhấn nút **CREATE** (hoặc **DEPLOY**) ở cuối trang để tạo Job.
8. Sau khi Job được tạo thành công, nhấp vào nút **EXECUTE** (hoặc **RUN**) để tiến hành chạy ETL nạp dữ liệu lần đầu tiên.

---

### Bước 9: Lập lịch tự động hàng ngày bằng Cloud Scheduler

1. Mở Menu bên trái -> chọn **Serverless** -> chọn **Cloud Scheduler**.
2. Nhấp vào nút **+ CREATE JOB** ở trên cùng.
3. Cấu hình lịch trình:
   - **Name**: `danang-etl-schedule`
   - **Region**: Chọn vùng **asia-southeast1**.
   - **Frequency**: Nhập biểu thức cron: `0 0 * * *` (chạy hàng ngày vào lúc 0 giờ).
   - **Timezone**: Chọn **Vietnam Time (ICT)** hoặc nhập `Asia/Ho_Chi_Minh`.
4. Nhấn **CONTINUE**.
5. Cấu hình Target:
   - **Target type**: Chọn **HTTP**.
   - **URL**: Nhập URL kích hoạt Job của bạn dưới dạng:  
     `https://asia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/capstone-project-2-group-4/jobs/danang-etl-job:run`
   - **HTTP method**: Chọn **POST**.
   - **Auth header**: Chọn **Add OAuth token**.
   - **Service account**: Chọn `mcp-toolbox-sa@capstone-project-2-group-4.iam.gserviceaccount.com`.
6. Nhấp vào nút **CREATE**.

---

### Bước 10: Triển khai AI Agent Service (ADK Web UI)

1. Mở Menu bên trái -> chọn **Serverless** -> chọn **Cloud Run**.
2. Nhấp vào nút **+ CREATE SERVICE**.
3. Để triển khai AI Agent Web UI, bạn có 2 tùy chọn thực hiện:
   * **Cách A (Sử dụng Image đã build sẵn - Khuyên dùng)**:
     - Chọn **Deploy one revision from an existing container image**.
     - Nhập đường dẫn Container image URL đã được build trước đó:
       `asia-southeast1-docker.pkg.dev/capstone-project-2-group-4/cloud-run-source-deploy/danang-agent-service:latest`
   * **Cách B (Triển khai và tự động build từ source qua Web Console)**:
     - Chọn **Deploy one revision from a source repository**.
     - Nhấn **SET UP WITH CLOUD BUILD** và chọn kho lưu trữ chứa thư mục `danang_hotel_agent` để cấu hình build tự động.
5. Thiết lập thông tin Service:
   - **Service name**: `danang-agent-service`
   - **Region**: Chọn vùng **asia-southeast1 (Singapore)**.
   - **Authentication**: Chọn **Allow unauthenticated invocations**.
6. Ở phần cấu hình biến môi trường, nhấp **+ ADD VARIABLE** và thêm các biến sau:
   - **`MCP_TOOLBOX_URL`**: Điền Service URL của dịch vụ `mcp-toolbox` đã copy ở **Bước 7**.
   - **`GOOGLE_GENAI_USE_VERTEXAI`**: Điền giá trị `True`.
7. Nhấp vào nút **CREATE** để hoàn thành quá trình build và triển khai Agent.
