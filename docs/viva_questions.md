# Cloud Computing Viva Voce — Questions & Model Answers

## Centralized Cloud Blood Bank & Emergency Registry
**Course:** Cloud Computing  
**Focus Areas:** Cloud Service Models, Cloud Deployment, Database Concurrency, Multi-tenancy, Security, System Architecture, and Testing.

---

### Part 1: Cloud Computing Foundations

#### Q1: What cloud service model does this project represent, and why?
**Answer:**  
This project represents **SaaS (Software-as-a-Service)** for the end users (hospitals, blood banks, and health administrators), because they access the application through a standard web browser without installing, maintaining, or provisioning any underlying infrastructure or application runtimes.  
From the developer perspective, it is deployed on a **PaaS (Platform-as-a-Service)** environment (such as Streamlit Community Cloud or Render), which automatically handles containerization, runtime execution, TLS certificate termination, and OS patching, leaving only the application code and database schema to the developer.

#### Q2: What is the difference between IaaS, PaaS, and SaaS in the context of this system?
**Answer:**
- **IaaS (Infrastructure-as-a-Service):** Provisioning raw virtual machines (e.g., AWS EC2, Azure VMs), where the developer is responsible for installing the OS, configuring Python, managing Nginx reverse proxies, setting up firewall rules, and handling operating system updates.
- **PaaS (Platform-as-a-Service):** Platforms like Streamlit Cloud, Heroku, or Render. The underlying VM and web server runtime are managed by the cloud provider. We provide our Git repository, requirements file, and environment configuration; the PaaS handles builds and deployments.
- **SaaS (Software-as-a-Service):** The finished Blood Bank application itself. Hospital doctors and blood bank technicians simply log in via HTTPS to coordinate blood units.

#### Q3: How does this application satisfy the 12-Factor App methodology for cloud-native software?
**Answer:**
1. **Codebase:** One single repository tracked in Git with multiple deployments (local dev, staging, cloud production).
2. **Dependencies:** Explicitly declared in `requirements.txt` with exact version pinning, isolating dependencies from system packages.
3. **Config:** Strict separation of config from code via environment variables (`DATABASE_URL`, `SECRET_KEY`, `APP_ENV`) loaded through `config/settings.py` and `python-dotenv`.
4. **Backing Services:** The database is treated as an attached resource. Swapping from local SQLite to cloud-hosted PostgreSQL requires changing only the `DATABASE_URL` connection string, zero code changes.
5. **Stateless Processes:** The web application processes are stateless; persistent state is stored entirely in the database tier, enabling seamless horizontal scale-out.
6. **Port Binding & Concurrency:** The app binds to a port provided by the cloud environment and scales out by spawning concurrent worker processes.

#### Q4: Why is statelessness critical for cloud applications, and how is it implemented here?
**Answer:**  
In cloud computing, application instances must be able to scale up, scale down, or crash and restart without losing user state. If session data or inventory locks were stored in local server memory or local text files, scaling out to multiple web containers behind a load balancer would cause synchronization failures (e.g., user logged into Container A wouldn't exist on Container B).  
In our project, all persistent state (lots, requests, users, reservations, audit logs) lives in the centralized relational database. In-memory session state in Streamlit is limited to transient UI rendering state.

#### Q5: What is Multi-Tenancy, and how is it handled in this project?
**Answer:**  
Multi-tenancy is an architectural principle where a single software instance serves multiple distinct customer organizations ("tenants").  
In our system, we use **Logical Multi-Tenancy with Row-Level Isolation**:
- Hospitals and blood banks share a common database schema and tables (`organizations`, `inventory_lots`, `emergency_requests`).
- Every critical record contains an `organization_id` foreign key.
- Security rules enforced in the service layer (`services/inventory_service.py`, `services/request_service.py`) verify that an authenticated user can only modify rows belonging to their designated `organization_id`.
- This provides cost efficiency while preserving tenant security.

#### Q6: How does cloud elasticity benefit a blood bank emergency registry?
**Answer:**  
Demand for blood registry lookups is naturally uneven. During normal operating hours, traffic consists of steady inventory updates. However, during a mass-casualty incident, natural disaster, or major accident, sudden spikes in emergency blood searches and reservation requests occur.  
Cloud elasticity allows the hosting platform to auto-scale application instances and database compute resources to handle sudden traffic surges without downtime or dropped requests.

---

### Part 2: Architecture & Database Design

#### Q7: Why did you choose a Relational Database (SQLAlchemy / PostgreSQL / SQLite) instead of a NoSQL database (e.g., MongoDB)?
**Answer:**  
A blood bank and emergency registry requires strict **ACID (Atomicity, Consistency, Isolation, Durability)** transactions:
1. **Financial and Life-Critical Integrity:** Inventory levels cannot have "eventual consistency" where two hospitals both believe they reserved the same unit of blood.
2. **Relational Constraints:** Foreign keys (`organization_id`, `request_id`, `lot_id`) ensure data integrity and prevent orphan records.
3. **Structured Queries:** Aggregations across blood groups, expiration date ranges, and organization types are natural relational queries.
NoSQL provides flexible schemas, but relational databases are superior when strict consistency, zero data loss, and transactional isolation are mandatory.

#### Q8: How does the system handle blood compatibility during emergency matching?
**Answer:**  
Blood compatibility is not purely a 1:1 match. While an exact match is ideal, transfusion medicine allows compatible substitutes during emergencies:
- **O-Negative** is the universal red blood cell donor and can be received by any blood group.
- **AB-Positive** is the universal recipient and can receive red cells from any ABO/Rh group.
- Rh-negative patients should only receive Rh-negative units, whereas Rh-positive patients can receive either Rh-positive or Rh-negative.  
Our `matching_service.py` implements these rules. When searching for candidates, users can toggle between "Exact Match Only" and "Emergency Compatible (ABO/Rh Rules)" to locate life-saving units when exact stock is unavailable.

#### Q9: How is distance calculated between hospitals and blood banks?
**Answer:**  
Distance is computed using the **Haversine Formula** implemented in `services/search_service.py`:
$$d = 2r \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
where $\phi$ is latitude and $\lambda$ is longitude in radians, and $r \approx 6371\text{ km}$ is Earth's radius.  
Blood banks with available compatible stock are returned sorted in ascending order of distance, ensuring the closest facility can be contacted and dispatched first.

#### Q10: How do you prevent expired blood units from being offered or reserved?
**Answer:**  
We prevent expired blood usage at multiple levels:
1. **Dynamic Query Filtering:** In `inventory_service.py` and `search_service.py`, SQL queries explicitly filter out any lot where `expiry_date <= CURRENT_DATE`.
2. **Transactional Validation:** In `reservation_service.py`, before reserving a unit, the service re-verifies `lot.is_expired` in Python logic. If expired, it raises a `ValidationError` and rejects the reservation.
3. **Dashboard Expiry Alerts:** The system highlights expiring lots within 7 days in yellow and expired lots in red for quarantine/disposal.

---

### Part 3: Concurrency, Transactions & Anti-Overselling

#### Q11: Explain the race condition that can occur during emergency blood reservation, and how your code prevents it.
**Answer:**  
**The Race Condition:**  
Suppose Blood Bank A has exactly 2 available units of O- blood. Hospital X and Hospital Y both query the database at 10:00:00 AM and see 2 available units. Both hospitals click "Reserve 2 Units" at 10:00:01 AM. Without concurrency protection, both transactions might read `available = 2`, both deduct 2, resulting in 4 units promised when only 2 exist (oversell).

**Our Prevention Mechanism:**  
In `services/reservation_service.py`:
1. The reservation logic executes inside an atomic database transaction (`with get_db() as db:`).
2. The code queries the current lot record and calculates `lot.available_units = lot.total_units - lot.reserved_units`.
3. If `requested_units > lot.available_units`, the transaction immediately aborts with an `InsufficientStockError`, rolling back all changes.
4. If sufficient, `lot.reserved_units` is incremented, the `Reservation` record is inserted with status `reserved`, and the `EmergencyRequest` status is updated to `matched`.
5. The entire block is committed atomically. On production PostgreSQL, row-level locking (`SELECT FOR UPDATE`) can be enabled for complete multi-worker serialization.

#### Q12: What happens when an emergency request is cancelled?
**Answer:**  
In `reservation_service.py` (`release_reservation` / `cancel_request`):
1. The user's authorization is verified (hospitals can only cancel their own requests; admins can cancel any).
2. The system locates all active reservations associated with the request.
3. For each active reservation, `lot.reserved_units` is decremented by the reserved amount, restoring available units to the general pool.
4. The reservation status is marked `released`, and the request status is set to `cancelled`.
5. An audit log entry is written recording the cancellation, timestamp, and user ID.
6. Double-release protection prevents releasing an already released or fulfilled reservation.

---

### Part 4: Security & Access Control

#### Q13: How are passwords stored and authenticated?
**Answer:**  
Passwords are **never stored in plain text**. We use `bcrypt` via Python's `bcrypt` library:
- When a user is created, a unique cryptographic salt is generated automatically by bcrypt, and the password is transformed into a one-way hash (`bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))`).
- During login, `bcrypt.checkpw(entered_password.encode(), stored_hash.encode())` verifies the password in constant time, preventing timing attacks.
- Passwords must meet minimum complexity requirements (at least 8 characters).

#### Q14: Explain the Role-Based Access Control (RBAC) matrix in your application.
**Answer:**
| Action / Resource | Admin | Blood Bank Staff | Hospital Staff |
| :--- | :---: | :---: | :---: |
| View System Dashboard & Global Metrics | Yes | No (Org-specific) | No (Org-specific) |
| Onboard New Organizations & Users | Yes | No | No |
| Add / Edit Blood Bank Inventory Lots | Yes | Own Org Only | No |
| Create Emergency Blood Requests | Yes | No | Own Hospital Only |
| Search Compatible Blood Across Registry | Yes | Yes | Yes |
| Reserve Units for a Request | Yes | Yes | Own Hospital Only |
| Mark Reservation as Fulfilled | Yes | Own Blood Bank Only | No |
| Cancel Emergency Request | Yes | No | Own Hospital Only |
| Inspect System-Wide Audit Logs | Yes | No | No |

#### Q15: How does the application protect against SQL Injection?
**Answer:**  
All database access is routed through **SQLAlchemy ORM** and parameterized queries. User inputs (such as search strings, blood group codes, lot numbers, and usernames) are passed as bound query parameters rather than string concatenation. This ensures that arbitrary SQL code entered in form inputs is treated strictly as literal data, eliminating SQL injection vulnerabilities.

---

### Part 5: Cloud Deployment & DevOps

#### Q16: How does the application transition from local SQLite to cloud PostgreSQL?
**Answer:**  
Through SQLAlchemy's dialect abstraction and environment variables:
- In `config/settings.py`, the application reads `os.getenv("DATABASE_URL")`.
- If `DATABASE_URL` is omitted, it defaults to `sqlite:///blood_bank.db` for zero-configuration local development.
- In cloud deployment (e.g., Render or Streamlit Cloud connected to Neon/Supabase), the cloud environment variable is set to:
  `postgresql://user:password@cloud-host:5432/blood_bank`
- Because our models use standard ANSI SQL datatypes and SQLAlchemy ORM abstractions, all tables, constraints, queries, and transactions run identically on PostgreSQL without altering a single line of business logic.

#### Q17: What is the purpose of `.env.example` vs `.env`?
**Answer:**  
- `.env` contains local development environment secrets (such as active secret keys or test credentials). It is explicitly listed in `.gitignore` so sensitive keys are never pushed to a public GitHub repository.
- `.env.example` is committed to version control and serves as a documented template showing team members and evaluators all required environment keys and sample values.

#### Q18: What is Cloud Shared Responsibility Model, and where does this project sit?
**Answer:**  
In cloud computing, security and operational duties are split between the cloud provider and the customer:
- **Cloud Provider (Streamlit Cloud / AWS / GCP):** Responsible for the security *of* the cloud (physical data centers, hypervisor virtualization, server hardware, power, physical network).
- **Application Developer (Our Responsibility):** Responsible for security *in* the cloud (application code, data sanitization, authentication, RBAC authorization logic, database schema, encryption of sensitive fields, and credential management).

---

### Part 6: Quality Assurance & Testing

#### Q19: How did you test the application, and what is your test coverage?
**Answer:**  
We implemented an automated test suite using `pytest` containing **60 test cases** across 4 dedicated test suites:
1. `test_inventory.py` (TC-01 to TC-06): Validates lot creation, negative unit rejection, past expiry rejection, cross-org update denial, and aggregation logic.
2. `test_requests.py` (TC-07 to TC-10, TC-14): Validates urgency prioritization, invalid blood group rejection, search filtering, and state machine transitions.
3. `test_reservations.py` (TC-09 to TC-12, TC-16): Validates atomic stock reservations, overselling prevention, release upon cancellation, and duplicate prevention.
4. `test_permissions.py` (TC-12 to TC-15): Validates password hashing, cross-tenant isolation, and data persistence across database sessions.
All 60 tests run against an in-memory SQLite database in under 2 seconds, ensuring fast, repeatable validation.

#### Q20: If an evaluator asks: "Can you run the tests right now?", what is the exact command?
**Answer:**  
Run:
```powershell
python -m pytest tests/ -v
```
This discovers and executes all 60 tests, printing each test name and its `PASSED` status.
