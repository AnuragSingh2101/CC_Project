# Future Development Plan for **Centralized Cloud Blood Bank & Emergency Registry**

This document outlines a short‑term roadmap for adding high‑impact, low‑effort features that enhance the cloud‑native capabilities, user experience, and security of the project.

---

## 1️⃣ Dark‑Mode Toggle & Responsive Layout

**Why:** Improves visual appeal, works on mobile devices, and gives a modern SaaS feel.

**Key Steps**
- Add a sidebar button in `app.py` to switch between `light` and `dark` themes using `st.session_state`.
- Use `st.set_page_config(layout="wide")` and inject a tiny CSS block that changes background and text colours based on the selected theme.
- Create `assets/custom.css` with media‑queries for screens < 600 px (mobile) to stack columns and shrink the sidebar.
- Update each page (`pages/*.py`) to use `st.container()`/`st.columns()` so the layout automatically adapts.
- Document the toggle in `START.md` with screenshots.

**Estimated effort:** ≤ 30 minutes.

---

## 2️⃣ Live Updates via WebSocket (or Server‑Sent Events)

**Why:** Demonstrates a real‑time cloud service where emergency requests appear instantly for all users.

**Key Steps**
1. **FastAPI side** – add a WebSocket endpoint `@app.websocket("/ws/updates")` in `api/main.py`. It accepts connections and streams JSON messages whenever a new emergency request is created.
2. **In‑memory event queue** – optional `collections.deque` that `request_service.create_request` pushes a payload into; the WebSocket loop reads from it.
3. **Streamlit side** – create `utils/ws_client.py` using the `websockets` library. The client runs in an `st.experimental_async` background task on the Emergency Registry page (`pages/3_Emergency_Registry.py`). When a message arrives it calls `st.experimental_rerun()` to refresh the table.
4. **UI indicator** – add a green “Live” dot in the page header; hide it if the socket disconnects.
5. **Docker** – expose port 8000 (already done) and ensure the service restarts on failure.
6. **Test** – start the stack, open two browser windows, create a request in one, observe auto‑refresh in the other.

**Estimated effort:** 1 – 2 hours.

---

## 3️⃣ Per‑User API Key Generation & Validation

**Why:** Allows external scripts or third‑party tools to interact with the backend without using JWT login, a common pattern for cloud APIs.

**Key Steps**
- **Database migration** – add a nullable, unique `api_key` column to the `user` table via Alembic (`alembic/versions/add_api_key.py`).
- **Endpoint** – create `POST /auth/api-key` that generates a UUID4 key, stores it for the authenticated user, and returns the key.
- **Auth dependency** – implement `def get_api_key(request: Request, db: Session = Depends(get_db))` that reads the `X-API-KEY` header, validates it, and raises `401` when missing/invalid.
- **Protect routes** – add `Depends(get_api_key)` to any public endpoint you want script access to (e.g., inventory search, reports). Keep JWT as the default for UI logins.
- **Streamlit page** – a new “My API Key” page that calls the endpoint and shows the key with a copy‑to‑clipboard button.
- **Documentation** – add a section in `START.md` explaining how to obtain and use the key.

**Estimated effort:** 1.5 hours.

---

## 4️⃣ Google OAuth2 “Login with Google”

**Why:** Provides a production‑grade, federated identity flow and removes the need for hard‑coded demo passwords.

**Key Steps**
1. **Create a Google OAuth client** (client‑id & client‑secret) in Google Cloud Console.
2. **Add dependencies** – `authlib` to `requirements.txt`.
3. **Environment variables** – add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env.example` and read them in `config/settings.py`.
4. **FastAPI routes** –
   - `GET /auth/google/login` → builds the Google consent URL and redirects.
   - `GET /auth/google/callback` → exchanges the `code` for an ID token, extracts the email, creates/updates a local user, and issues a JWT (re‑use existing token helper).
5. **Streamlit integration** – a “Login with Google” button on the login page that opens the FastAPI login URL in a new tab. The callback returns a tiny HTML page with a script that stores the JWT in `localStorage` and redirects back to `http://localhost:8501/?token=…`. Streamlit reads that query param on start and stores it in `st.session_state`.
6. **Fallback** – keep the original username/password login for users without Google accounts.
7. **Docs** – add a quick‑start guide in `START.md` for setting up the OAuth client.

**Estimated effort:** 2 – 3 hours.

---

## 📅 Timeline (Assuming ~4 h of work per day)
| Day | Tasks |
|-----|-------|
| **Day 1** | Implement Dark‑Mode toggle & responsive CSS. Test on desktop & mobile. Commit & document. |
| **Day 2** | Add WebSocket endpoint, client helper, and integrate into the Emergency Registry page. Verify live updates across two browsers. |
| **Day 3** | Create API‑key migration, endpoint, auth dependency, and Streamlit “My API Key” page. Update docs. |
| **Day 4** | Set up Google OAuth client, add FastAPI routes, Streamlit button, and fallback flow. Test end‑to‑end login.
| **Day 5** | Final regression test, run full CI, update `START.md` with all new features, push to GitHub. |

---

## ✅ Success Criteria
- **UI** – dark mode works, layout adapts to phones.
- **Real‑time** – new emergency requests appear instantly for all connected users.
- **API** – a user can generate a static API key and use it to call protected endpoints (curl works).
- **OAuth** – a user can log in via Google, receive a JWT, and access the app without a password.
- **Documentation** – `START.md` includes usage instructions for each new feature.
- **CI** – the GitHub Actions workflow passes after adding new dependencies.

---

*Feel free to adjust the timeline or drop any feature that no longer matches your project scope.*

