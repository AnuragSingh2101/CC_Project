# Project Report

## Centralized Cloud Blood Bank & Emergency Registry

**Subject:** Cloud Computing  
**Academic Year:** 2026–27  
**Institution:** [Your Institution Name]  
**Student:** [Your Name]  
**Roll No:** [Your Roll No]

---

## 1. Abstract

This project presents a centralized, cloud-deployable web application for managing blood bank inventory and coordinating emergency blood requests across hospitals and blood banks. The application demonstrates core cloud computing concepts including centralized data access, managed database connectivity, role-based authentication, environment-based configuration, and deployment on a public cloud platform. The system allows blood bank staff to maintain inventory records, hospitals to submit and track emergency requests, and administrators to monitor system-wide activity. The prototype uses synthetic data for demonstration and makes no clinical compatibility claims.

---

## 2. Introduction

Blood is a critical medical resource that cannot be manufactured artificially. Effective blood bank management is essential for saving lives during emergencies. Currently, hospitals and blood banks often operate in isolation, relying on phone calls and manual coordination. This fragmentation causes delays and inventory mismatches.

A centralized cloud platform can bridge this gap by providing real-time visibility into blood availability, enabling digital request submission, and reducing the time between a medical need and supply fulfillment.

---

## 3. Problem Statement

Existing blood management systems face several challenges:

- **Fragmented data**: Each blood bank maintains its own records with no shared visibility.
- **Manual coordination**: Emergency requests require phone calls and manual matching.
- **Expiry waste**: Without centralized tracking, blood units expire before use.
- **No audit trail**: Status changes and inventory movements are not systematically recorded.
- **Limited accessibility**: Hospital staff cannot search for available blood banks digitally.

---

## 4. Objectives

1. Build a centralized web application accessible from any browser.
2. Enable blood banks to maintain and update inventory with expiry tracking.
3. Allow hospitals to submit, track, and cancel emergency blood requests.
4. Implement a matching service to find candidate inventory lots for a request.
5. Implement atomic reservation logic that prevents inventory overselling.
6. Provide an administrator dashboard with real-time metrics and alerts.
7. Demonstrate cloud deployment and cloud computing concepts.
8. Implement role-based authorization and secure password management.
9. Write an automated test suite covering all critical workflows.

---

## 5. Existing System

Traditional blood bank systems typically involve:
- Paper-based or Excel inventory registers
- Phone-based inter-hospital communication
- No centralized query interface
- No automated expiry alerts
- No concurrent request handling

Limitations: slow, error-prone, no audit trail, and not accessible remotely.

---

## 6. Proposed System

A cloud-hosted web application with:
- Browser-based access for all stakeholders
- Role-specific dashboards
- Real-time database-driven inventory
- Automated expiry and low-stock alerts
- Digital request submission and tracking
- Atomic, transactional reservation management
- Full audit log

---

## 7. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | User authentication with username and password |
| FR-02 | Role-based access: admin, blood_bank, hospital |
| FR-03 | Blood bank can create, view, and update inventory lots |
| FR-04 | Inventory tracks blood group, units, and expiry date |
| FR-05 | Hospital can submit emergency blood requests |
| FR-06 | Requests have urgency levels: routine, urgent, critical |
| FR-07 | Blood bank search by blood group, city, and availability |
| FR-08 | Matching service returns candidate lots for a request |
| FR-09 | Blood bank can reserve units from their inventory |
| FR-10 | Reservation cannot exceed available stock |
| FR-11 | Hospital can cancel eligible requests |
| FR-12 | Cancellation releases all active reservations |
| FR-13 | Admin views system-wide metrics and audit history |
| FR-14 | Low-stock and near-expiry alerts on admin dashboard |
| FR-15 | Expired lots excluded from available inventory |

---

## 8. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | Passwords stored as bcrypt hashes |
| NFR-02 | Authorization enforced in service layer |
| NFR-03 | Database transactions for all inventory mutations |
| NFR-04 | No negative inventory quantities |
| NFR-05 | Input validation on all user-provided data |
| NFR-06 | Audit log for all significant actions |
| NFR-07 | Parameterized queries via ORM |
| NFR-08 | Configurable via environment variables |
| NFR-09 | SQLite for local development; PostgreSQL for cloud |
| NFR-10 | Automated test suite with ≥ 60 tests |

---

## 9. Cloud Computing Concepts Demonstrated

### 9.1 SaaS (Software as a Service)
The application is hosted on Streamlit Community Cloud and accessible via a public URL. Users do not install any software — they access the service through a browser.

### 9.2 Centralized Data Access
All organizations (blood banks, hospitals, admin) access a single shared database. Inventory and requests are visible in real time without data duplication.

### 9.3 Scalability
The architecture supports scaling by switching the database from SQLite to a managed PostgreSQL service. The Streamlit application can be deployed on cloud infrastructure with more resources.

### 9.4 Availability
Streamlit Community Cloud provides high-availability hosting for the application layer. A managed PostgreSQL database provides database-level availability beyond what a local SQLite file can offer.

### 9.5 Environment-Based Configuration
No credentials are hardcoded. Configuration is loaded from environment variables (local) or Streamlit Secrets (cloud). This follows the twelve-factor app methodology.

### 9.6 Persistence and Durability
- **SQLite**: Data persists in a file on the server filesystem. Not suitable for ephemeral cloud deployments.
- **PostgreSQL**: Data persists in a managed cloud database with replication and backup support.

### 9.7 Authentication and Access Control
Role-based access control is enforced at the service layer. Passwords are hashed with bcrypt.

### 9.8 Logging and Monitoring
All significant actions are written to an audit log table. The admin dashboard displays live system health metrics.

---

## 10. Architecture

### 10.1 System Architecture

```
[Browser] → HTTPS → [Streamlit App on Cloud]
                          ↓
                    [Service Layer]
                     Auth · Inventory · Requests · Reservations · Matching
                          ↓
                    [SQLAlchemy ORM]
                          ↓
                [SQLite (local) / PostgreSQL (cloud)]
```

### 10.2 Layer Descriptions

- **Presentation Layer**: Streamlit pages handle UI, forms, and state.
- **Service Layer**: Contains business logic, authorization, and validation.
- **Data Access Layer**: SQLAlchemy ORM with parameterized queries.
- **Database Layer**: SQLite for development; PostgreSQL for cloud.

See `docs/diagrams/architecture.mmd` for the full Mermaid diagram.

---

## 11. Database Design

### Entities and Relationships

| Table | Purpose |
|-------|---------|
| organizations | Blood banks and hospitals |
| users | Authenticated users with roles |
| inventory_lots | Blood units with expiry dates |
| emergency_requests | Hospital blood requests |
| reservations | Links requests to inventory lots |
| audit_logs | System event history |

See `docs/diagrams/er_diagram.mmd` for the full ER diagram.

### Key Constraints

- `users.username` is unique
- `inventory_lots.units_reserved <= units_total` (CHECK constraint)
- `inventory_lots.units_total >= 0`, `units_reserved >= 0`
- `emergency_requests.units_requested > 0`
- `reservations.units_reserved > 0`
- Blood group values restricted to 8 standard ABO/Rh groups
- Role values restricted to `admin`, `hospital`, `blood_bank`

---

## 12. Implementation Details

### 12.1 Authentication

Passwords are hashed using bcrypt with a randomly generated salt per user. The `User.check_password()` method uses `bcrypt.checkpw()` for constant-time comparison.

```python
def set_password(self, plain_password: str):
    salt = bcrypt.gensalt()
    self.password_hash = bcrypt.hashpw(
        plain_password.encode("utf-8"), salt
    ).decode("utf-8")
```

### 12.2 Atomic Reservation

The `make_reservation()` function in `reservation_service.py`:
1. Loads the inventory lot in the same transaction
2. Checks `available_units = units_total - units_reserved`
3. Raises `ValueError` if insufficient
4. Updates `units_reserved` in-place
5. Creates the `Reservation` record
6. Updates the request status
7. All within a single SQLAlchemy session (single transaction)

### 12.3 Matching Service

The matching engine uses a configurable `CANDIDATE_SEARCH_ORDER` dictionary. It does NOT perform clinical compatibility validation. Results are labeled "candidates" and include an explicit disclaimer.

### 12.4 Expiry Tracking

The `InventoryLot.is_expired` property compares `expiry_date` against `date.today()`. The `get_all_lots()` service function filters expired lots by default. Expired lots are still stored and visible with `include_expired=True`.

---

## 13. UI Screenshots Placeholders

*Screenshots should be captured from the running application and inserted here.*

1. **Login Page** — Username/password form with demo account info
2. **Admin Dashboard** — 6 metric cards, 4 charts, low-stock and near-expiry alerts
3. **Blood Inventory** — Filterable table, add lot form, update quantity form
4. **Emergency Registry** — Request form, request history table, reservation panel
5. **Blood Bank Search** — Search form with results table
6. **Reports** — Tabs for inventory summary, request analytics, and audit log

---

## 14. Testing Methodology

### Test Infrastructure

- Framework: pytest 9.1.1
- Database: In-memory SQLite via SQLAlchemy `StaticPool`
- Isolation: Each test function uses a transactional fixture that rolls back after the test
- No real database is touched during testing

### Test Categories

| File | Description | Tests |
|------|-------------|-------|
| test_inventory.py | Creation, update, validation, expiry | 16 |
| test_requests.py | Creation, search, status transitions, auth | 18 |
| test_reservations.py | Reservation, release, fulfillment, oversell | 16 |
| test_permissions.py | Auth, cross-org access, persistence | 10 |

---

## 15. Actual Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.7.0
collected 60 items

tests/test_inventory.py::TestInventoryCreation::test_create_valid_lot PASSED
tests/test_inventory.py::TestInventoryCreation::test_create_lot_all_blood_groups PASSED
tests/test_inventory.py::TestInventoryCreation::test_create_lot_invalid_blood_group PASSED
tests/test_inventory.py::TestInventoryCreation::test_create_lot_negative_units PASSED
tests/test_inventory.py::TestInventoryCreation::test_create_lot_past_expiry PASSED
tests/test_inventory.py::TestInventoryCreation::test_create_lot_wrong_org_type PASSED
tests/test_inventory.py::TestInventoryUpdate::test_update_total_units PASSED
tests/test_inventory.py::TestInventoryUpdate::test_update_refuses_negative PASSED
tests/test_inventory.py::TestInventoryUpdate::test_update_refuses_below_reserved PASSED
tests/test_inventory.py::TestInventoryUpdate::test_update_cross_org_denied PASSED
tests/test_inventory.py::TestAvailableUnits::test_available_units_calculation PASSED
tests/test_inventory.py::TestAvailableUnits::test_available_units_zero_when_fully_reserved PASSED
tests/test_inventory.py::TestAvailableUnits::test_is_expired_false_for_future PASSED
tests/test_inventory.py::TestAvailableUnits::test_is_expired_true_for_past PASSED
tests/test_inventory.py::TestAvailableUnits::test_expired_excluded_from_get_lots PASSED
tests/test_inventory.py::TestAvailableUnits::test_available_units_by_group_aggregation PASSED
... [44 more tests, all PASSED] ...

============================= 60 passed in 1.73s ==============================
```

**Result: 60/60 tests passed. 0 failures. 0 errors.**

---

## 16. Cloud Deployment

### Deployment Platform

Target: Streamlit Community Cloud (share.streamlit.io) — free tier

### Local Deployment (Verified)

The application runs successfully on the local machine with:
```powershell
streamlit run app.py
```
Accessible at `http://localhost:8501`.

### Cloud Deployment Steps

1. Push repository to GitHub (excluding `.env` and `*.db`)
2. Create account at share.streamlit.io
3. Connect GitHub repository
4. Set entrypoint to `app.py`
5. Configure secrets (DATABASE_URL, SECRET_KEY, etc.)
6. Deploy and test public URL

### SQLite Persistence Limitation

Streamlit Community Cloud uses an ephemeral filesystem. A SQLite database may be reset on container restart. For persistent cloud storage, configure a managed PostgreSQL service (Neon, Supabase, ElephantSQL — all offer free tiers).

### Deployment Status

*Document the actual deployment status here after attempting cloud deployment.*

---

## 17. Security and Privacy

- Passwords: bcrypt hashed with random salt
- No plaintext passwords stored
- Authorization: enforced at service layer, not just UI
- Input validation: all user inputs validated before database writes
- ORM queries: parameterized, not raw SQL strings
- Secrets: loaded from environment or Streamlit Secrets
- Audit log: records all significant state changes
- No real patient data: all data is synthetic

**Production requirements** (not implemented in this prototype):
- HTTPS/TLS (provided by cloud platform)
- Rate limiting and brute-force protection
- Comprehensive security audit
- Data protection compliance (HIPAA, GDPR as applicable)
- Clinical validation by qualified medical professionals
- Regular database backups and disaster recovery

---

## 18. Limitations

1. **SQLite concurrency**: Under concurrent writes, transactions serialize. Not suitable for high-traffic production use without PostgreSQL.
2. **SQLite cloud persistence**: Ephemeral filesystem on Streamlit Community Cloud means SQLite data may be lost on restart.
3. **No real-time push**: Streamlit requires page refresh to see updates from other users.
4. **Single server**: No horizontal scaling without a shared database.
5. **Medical disclaimer**: No clinical compatibility validation. Matching is for search purposes only.
6. **No SMS/email notifications**: Emergency alerts are not sent automatically.
7. **No geographic map**: Distance calculation uses the Haversine formula; no road routing or visual map.

---

## 19. Future Enhancements

1. Real-time notifications (SMS/email) for critical requests
2. PostgreSQL full-text search for blood bank lookup
3. Geographic map visualization of blood banks
4. Mobile-responsive UI improvements
5. API endpoints for external integration
6. Automated expiry-based alerts and batch jobs
7. Role-based multi-tenant data isolation
8. Integration with national blood bank registries

---

## 20. Conclusion

This project successfully demonstrates a centralized, cloud-deployable blood bank management system using modern Python web technologies and cloud computing concepts. The application implements role-based access control, transactional inventory management, emergency request coordination, and a candidate matching service — all with 60 automated tests confirming correctness. The architecture supports transition from local SQLite to cloud-hosted PostgreSQL without code changes.

---

## 21. References

1. Streamlit Documentation — https://docs.streamlit.io
2. SQLAlchemy Documentation — https://docs.sqlalchemy.org
3. bcrypt Library — https://pypi.org/project/bcrypt/
4. Plotly Python — https://plotly.com/python/
5. pytest Documentation — https://docs.pytest.org
6. Twelve-Factor App Methodology — https://12factor.net
7. Haversine Formula — https://en.wikipedia.org/wiki/Haversine_formula
8. ABO Blood Group System — https://en.wikipedia.org/wiki/ABO_blood_group_system (for reference only; no clinical validation implemented)
