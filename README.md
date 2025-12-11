# Marketing Automation Module Implementation Report

## Implementation Summary

### Scope
- Implemented the Marketing Automation module as defined in the architecture.
- Sales, Service, Auth Gateway, and Data Intelligence are modeled conceptually but not coded in this project.
- Authentication is embedded in the Flask app (session-based login) to keep the prototype self-contained.

### Architecture Mapping
The implementation follows the proposed architecture:

**Module View**
- **Presentation Layer (View):** Flask Templates (`templates/`).
- **Business Logic Layer (Controller):** `services.py` (Business Logic).
- **Data Access Layer (Model):** `models.py` with SQLAlchemy. This corresponds to the MA box in the decomposition diagram.

**Component & Connector View**
- **Client-Server:** Browser interacts with Flask via HTTP/JSON (`routes.py`).
- **Publish-Subscribe:** Redis EventBus is used for broadcasting events (e.g., `CampaignCreated`).
- **Shared Data:** Single SQL database with different schemas for each module (SQLite for development, PostgreSQL-ready schema).

**Deployment View**
- Developed as a single Flask process + SQLite on one host.
- Target deployment matches the 3-tier diagram (browser, Python app server, PostgreSQL DB).

**Design Patterns**
- **MVC:** Models (data), Templates (views), Routes (controllers).
- **Microservice:** Independent Marketing Automation service.
- **Factory:** `create_app` for application initialization.
- **Repository:** Data access abstraction in services.

## Key Features Implemented
- **Authentication:** `/auth/login`, `/auth/logout`, `/auth/me` pages check the user-password matching with SHA-256 password hash; We have a demo user with a username : `admin` and password: `admin123`.
- **Customers:** CRUD + pagination/search; unified customer profile fields (demographics, behavioral, purchase history, LTV, engagement score).
- **Segmentation:** JSON-based rules with AND/OR; `evaluate_segment_criteria` and `refresh_segment` to compute membership counts.
- **Campaigns:** Create/Update/List/Get; launch/pause/complete; launch simulates delivery/opens/clicks/conversions/revenue and stores in `CampaignResult`.
- **Analytics:** Overview of KPIs, ROI report, funnel data, segment performance gives us analysis of performance; all derived from `CampaignResult` records.
- **Events:** `CampaignCreated` (and launch) published to Redis channel `crm_events` (Event Bus).

## API & Architecture Relationships
The following table details how the API endpoints serve the architecture:

| Endpoint | Method | Architecture Flow | Description |
|---|---|---|---|
| `/auth/login` | POST | Controller → Service→ DB | Authenticates user credentials and establishes a session. |
| `/customers` | GET | Controller → Service→ DB | Pulls up customer data in pages for the Customer View. |
| `/segments/<id>/refresh` | POST | Controller → Engine→ DB | Pulls up customer data in pages for the Customer View. |
| `/campaigns/<id>/launch` | POST | Controller → Service→ EventBus | Updates the campaign's status, creates sample performance data, and sends a message to Redis to notify other services. |
| `/analytics/roi` | GET | Controller → Analytics Service | Gathers data from campaign results to prepare the dashboard. |

## Quality Attributes
- **Security:** We check users with a session key and hidden passwords; a security wall (route guard) is used; the user screen cannot access the database directly.
- **Performance/Scalability:** Lightweight REST; async pub/sub for cross-module notifications; simulated metrics generation.
- **Modifiability:** Clear separation of routes/services/models; configuration in `config.py`.
- **Data Consistency:** Single database schema for MA; segment refresh ensures cached counts align with rules.

## Limitations & Future Work
- Auth Gateway and external Auth Service are conceptual.
- Sales/Service subscribers to Redis are not implemented.
- Data Intelligence (CLV/churn/NBA) is not implemented beyond stored fields.
- We use a simple database (SQLite) for testing, but the final version should use a stronger one (PostgreSQL).

## Run Instructions
```bash
cd crm-system/marketing_service
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m flask run --port 5003
```
Open [http://localhost:5003](http://localhost:5003)
